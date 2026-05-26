"""Launcher that works when the shell is already inside the `vocra/` folder."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parent
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    from vocra.cli.main import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
