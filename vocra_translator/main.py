from __future__ import annotations

import sys

from vocra_translator.main_window import run_app


def main() -> int:
    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
