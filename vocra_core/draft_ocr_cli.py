from __future__ import annotations

import sys

from vocra_core.draft_ocr import _run_draft_ocr_internal


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("ERROR\tMissing project_dir", flush=True)
        return 2

    project_dir = argv[1]

    def callback(current: int, total: int | None, message: str) -> None:
        resolved_total = int(total if total is not None else max(current, 1))
        safe_message = str(message).encode("ascii", "backslashreplace").decode("ascii")
        print(f"PROGRESS\t{int(current)}\t{resolved_total}\t{safe_message}", flush=True)

    try:
        count = _run_draft_ocr_internal(project_dir, callback=callback)
    except Exception as exc:
        print(f"ERROR\t{exc}", flush=True)
        return 1

    print(f"RESULT\t{count}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
