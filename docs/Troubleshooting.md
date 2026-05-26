# Troubleshooting

## Install fails because `pip` does not understand `--group`

The repository currently uses dependency groups in `pyproject.toml`.

Try:

```bash
python -m pip install --upgrade pip
python -m pip install . --group dev
```

If your `pip` is too old for dependency groups, either upgrade `pip` first or install the listed dependencies manually from `pyproject.toml`.

## `pytest` is not installed

Some environments in this repository history did not have `pytest` installed even though the dev dependency group includes it.

Use the baseline test command:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

You can also run Ruff independently:

```bash
ruff check vocra tests
```

## I still see legacy VideOCR files in the repository

That can be normal.

The active runtime/package for new work is VOCra:

```bash
python -m vocra --help
python -m vocra.cli.main --help
```

VOCra no longer needs `VideOCR.py` or `CLI/videocr` at runtime, but the repository may still keep some legacy files around as algorithm references while migration work continues.

## `prepare run` fails because there is no crop zone

Prepare needs either:

- one or more `--crop-zone x,y,width,height` values, or
- `--use-fullframe`

Example:

```bash
python -m vocra.cli.main prepare run --project C:\path\to\episode01.vocra --crop-zone 130,780,1660,220 --detector fake
```

## `prepare run` fails because PaddleOCR detector configuration is missing

The real Prepare path defaults to `paddleocr-text-detection`, which may need:

- a valid PaddleOCR executable path
- a valid detector model directory
- local PaddleOCR installation/configuration

For pipeline/dev validation without external detector setup, use:

```bash
python -m vocra.cli.main prepare run --project C:\path\to\episode01.vocra --crop-zone 130,780,1660,220 --detector fake
```

## OCR run cannot find representative images

OCR consumes prepared subtitle segment artifacts. If representative images are missing, OCR is expected to fail.

Check that:

- Prepare completed successfully
- `prepare/subtitle_segments.jsonl` exists
- the representative image paths referenced by each segment still exist on disk

## `ocr resume-failed` or `ocr rerun-empty` fails

These commands target an existing OCR run.

Check that:

- `--run-id` points to an existing directory under `ocr/runs/`
- the selected OCR run belongs to the same project
- the backend/config you supplied matches the intended run

## GUI does not open or behaves differently from the docs

The GUI exists and is usable, but Phase 20 still includes interactive smoke validation and release polish work.

Useful checks:

```bash
python -m vocra.cli.main gui --help
python -m vocra.cli.main --help
```

If the shell opens but a workflow feels unstable, check [progress.md](progress.md) for the latest known status and open gaps.

## Output behavior does not match old one-click VideOCR expectations

That is expected.

VOCra is intentionally staged and artifact-driven:

```text
Project -> Prepare -> OCR -> Review -> Package
```

The goal is not to reproduce the old one-click UX. The goal is durable artifacts, replaceable OCR backends, and correct timing ownership.
