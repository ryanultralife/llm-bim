"""``llmbim`` console script."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("llmbim — LLM-native BIM CLI (MVP scaffolding)")
        print("Usage: llmbim version | help")
        return 0
    if args[0] == "version":
        from llmbim import __version__

        print(__version__)
        return 0
    print(f"Unknown command: {args[0]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
