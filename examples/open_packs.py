#!/usr/bin/env python3
"""One-click pack portal: serve examples/output and open the clickable HTML.

Usage:
  python examples/open_packs.py                 # portal list
  python examples/open_packs.py mineclean_studio
  python examples/open_packs.py studio          # alias → mineclean_studio
  python examples/open_packs.py studio --viewer # 3D viewer
  python examples/open_packs.py --list

Double-click OPEN.bat / OPEN_MINECLEAN.bat from the repo root.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "output"
DEFAULT_PACK = "mineclean_studio"

ALIASES = {
    "studio": DEFAULT_PACK,
    "mc": DEFAULT_PACK,
    "mclean": DEFAULT_PACK,
    "mineclean": DEFAULT_PACK,  # full studio is what you want most of the time
    "skid": "mineclean",  # thin skid pack if you really want it
    "proto": "proto10",
    "p10": "proto10",
    "rmm": "rmm_otd",
    "rmm-otd": "rmm_otd",
    "otd": "rmm_otd",
    "battery": "rmm_otd",
}

NOTES = {
    "mineclean_studio": "MB-MCLEAN full apparatus — product stills + 3D + stamp sheets",
    "mineclean_full_apparatus": "Component apparatus densify (tubes / wire paths)",
    "mineclean": "Earlier thin skid pack",
    "mineclean_multilayer": "Multilayer intermediate",
    "proto10": "Proto-10 separator stress pack",
    "intec": "INTEC facility construction pack",
    "template_office": "Office template",
    "rmm_otd": "RMM-OTD cascade — STEP/glTF/IFC + 2D sheets + gallery.html",
}


def discover_packs(out: Path = OUT) -> list[dict]:
    packs: list[dict] = []
    if not out.is_dir():
        return packs
    for d in sorted(out.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        idx = (d / "index.html").is_file()
        viewer = (d / "viewer3d.html").is_file()
        if not idx and not viewer:
            continue
        verify_ok = None
        vpath = d / "VERIFY.json"
        if vpath.is_file():
            try:
                verify_ok = bool(json.loads(vpath.read_text(encoding="utf-8")).get("ok"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                verify_ok = None
        packs.append(
            {
                "name": d.name,
                "index": idx,
                "viewer3d": viewer,
                "verify_ok": verify_ok,
                "note": NOTES.get(d.name, ""),
            }
        )
    return packs


def write_portal(out: Path, packs: list[dict]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "packs.json").write_text(json.dumps(packs, indent=2) + "\n", encoding="utf-8")


def pick_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"No free port near {preferred}")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        try:
            code = str(args[1]) if len(args) > 1 else ""
        except Exception:
            code = ""
        if code.startswith(("4", "5")):
            super().log_message(fmt, *args)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def resolve_pack(name: str | None, packs: list[dict]) -> str | None:
    if not name:
        return None
    names = {p["name"] for p in packs}
    if name in names:
        return name
    key = name.lower().strip()
    if key in ALIASES and ALIASES[key] in names:
        return ALIASES[key]
    matches = [p["name"] for p in packs if p["name"].startswith(name)]
    if len(matches) == 1:
        return matches[0]
    return None


def pack_url_path(pack: str, viewer: bool) -> str:
    d = OUT / pack
    if viewer and (d / "viewer3d.html").is_file():
        return f"/{pack}/viewer3d.html"
    if (d / "index.html").is_file():
        return f"/{pack}/index.html"
    if (d / "viewer3d.html").is_file():
        return f"/{pack}/viewer3d.html"
    raise SystemExit(f"No index.html or viewer3d.html in {d}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Open llm-bim pack HTML (local server)")
    ap.add_argument("pack", nargs="?", default=None, help="Pack name or alias (studio, proto, …)")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--viewer", action="store_true", help="Open viewer3d.html for the pack")
    args = ap.parse_args()

    packs = discover_packs(OUT)
    if args.list:
        for p in packs:
            flags = []
            if p["index"]:
                flags.append("index")
            if p["viewer3d"]:
                flags.append("3d")
            if p["verify_ok"] is True:
                flags.append("VERIFY")
            print(f"  {p['name']:32}  {' '.join(flags)}")
        return 0

    if not packs:
        print(f"No packs with index.html under {OUT}", file=sys.stderr)
        return 1

    write_portal(OUT, packs)

    path = "/"
    if args.pack:
        resolved = resolve_pack(args.pack, packs)
        if not resolved:
            print(f"Unknown pack {args.pack!r}. Try:", file=sys.stderr)
            for p in packs:
                print(f"  {p['name']}", file=sys.stderr)
            print("Aliases: studio, mc, mineclean, proto, skid", file=sys.stderr)
            return 1
        if resolved != args.pack:
            print(f"[info] {args.pack!r} → {resolved}")
        path = pack_url_path(resolved, args.viewer)

    host = args.host
    port = pick_port(host, args.port)
    url = f"http://{host}:{port}{path}"

    handler = partial(QuietHandler, directory=str(OUT))
    httpd = ThreadingHTTPServer((host, port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    # Durable re-engage note (agents + humans open this after work)
    reengage = {
        "portal": f"http://{host}:{port}/",
        "open_now": url,
        "default_mineclean": f"http://{host}:{port}/mineclean_studio/",
        "bat": ["OPEN.bat", "OPEN_MINECLEAN.bat"],
        "root": str(OUT),
    }
    try:
        (OUT / "REENGAGE.json").write_text(
            json.dumps(reengage, indent=2) + "\n", encoding="utf-8"
        )
        (OUT / "REENGAGE.txt").write_text(
            f"REENGAGE: {url}\n"
            f"PORTAL:   http://{host}:{port}/\n"
            f"MINECLEAN: http://{host}:{port}/mineclean_studio/\n"
            f"Double-click OPEN.bat or OPEN_MINECLEAN.bat from repo root.\n",
            encoding="utf-8",
        )
        (ROOT / "REENGAGE.txt").write_text(
            f"REENGAGE: {url}\n"
            f"PORTAL:   http://{host}:{port}/\n"
            f"MINECLEAN: http://{host}:{port}/mineclean_studio/\n"
            f"Double-click OPEN.bat or OPEN_MINECLEAN.bat\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[warn] could not write REENGAGE.txt: {e}")

    print()
    print("=" * 56)
    print(f"  REENGAGE:  {url}")
    print(f"  PORTAL:    http://{host}:{port}/")
    if (OUT / DEFAULT_PACK / "index.html").is_file():
        print(f"  MINECLEAN: http://{host}:{port}/{DEFAULT_PACK}/")
    print("=" * 56)
    print(f"Root: {OUT}")
    print("Ctrl+C to stop. Leave this running while you browse.")
    if not args.no_browser:
        time.sleep(0.2)
        webbrowser.open(url)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
