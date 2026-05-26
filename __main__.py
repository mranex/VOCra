"""Allow `python -m vocra` to dispatch to the CLI."""

from __future__ import annotations

from vocra.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
