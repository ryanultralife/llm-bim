"""Zip a deliverables directory for download."""

from __future__ import annotations

import zipfile
from pathlib import Path


def zip_pack(out_dir: str | Path, zip_path: str | Path | None = None) -> Path:
    out = Path(out_dir)
    zp = Path(zip_path) if zip_path else out / "deliverables.zip"
    with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in out.rglob("*"):
            if f.is_file() and f.resolve() != zp.resolve():
                zf.write(f, f.relative_to(out).as_posix())
    return zp
