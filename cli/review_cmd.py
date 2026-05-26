"""Review-related CLI commands for VOCra."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vocra.app.ocr_compare_service import (
    apply_ocr_comparison_choice,
    find_ocr_comparison_item,
    load_ocr_comparison_summary,
)
from vocra.core.project.workspace import ProjectWorkspaceError
from vocra.core.review.service import (
    load_review_items,
    save_review_batch,
    save_review_edit,
)


def configure_review_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    review_parser = subparsers.add_parser(
        "review",
        help="Inspect and edit review-state artifacts for an OCR run.",
    )
    review_subparsers = review_parser.add_subparsers(dest="review_command")

    list_parser = review_subparsers.add_parser(
        "list",
        help="List review items for an OCR run.",
    )
    list_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    list_parser.add_argument(
        "--prepare-run",
        default="prepare_default",
        help="Prepare run identifier. Use `prepare_default` for top-level prepare artifacts.",
    )
    list_parser.add_argument("--ocr-run", required=True, help="OCR run identifier.")
    list_parser.add_argument(
        "--filter",
        default="all",
        choices=(
            "all",
            "pending",
            "accepted",
            "edited",
            "rejected",
            "unreviewed",
            "errors",
            "empty",
            "suspicious",
        ),
        help="Review filter to apply.",
    )
    list_parser.set_defaults(func=_handle_review_list)

    set_parser = review_subparsers.add_parser(
        "set",
        help="Create or update a review-state row for one segment.",
    )
    set_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    set_parser.add_argument("--ocr-run", required=True, help="OCR run identifier.")
    set_parser.add_argument("--segment", required=True, help="Segment identifier to edit.")
    set_parser.add_argument(
        "--status",
        required=True,
        choices=("pending", "accepted", "edited", "rejected"),
        help="Review status to store.",
    )
    set_parser.add_argument(
        "--text",
        help="Edited text to store. Defaults to the OCR text when omitted.",
    )
    set_parser.add_argument(
        "--notes",
        default="",
        help="Optional review notes.",
    )
    set_parser.set_defaults(func=_handle_review_set)

    batch_set_parser = review_subparsers.add_parser(
        "batch-set",
        help="Create or update review-state rows for multiple segments at once.",
    )
    batch_set_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    batch_set_parser.add_argument(
        "--prepare-run",
        default="prepare_default",
        help="Prepare run identifier. Use `prepare_default` for top-level prepare artifacts.",
    )
    batch_set_parser.add_argument("--ocr-run", required=True, help="OCR run identifier.")
    batch_set_parser.add_argument(
        "--segment",
        action="append",
        default=[],
        help="Segment identifier to update. Repeat to target multiple segments.",
    )
    batch_set_parser.add_argument(
        "--filter",
        choices=(
            "all",
            "pending",
            "accepted",
            "edited",
            "rejected",
            "unreviewed",
            "errors",
            "empty",
            "suspicious",
        ),
        help="Optional review filter used to choose segments for the batch update.",
    )
    batch_set_parser.add_argument(
        "--status",
        required=True,
        choices=("pending", "accepted", "edited", "rejected"),
        help="Review status to store for all selected segments.",
    )
    batch_set_parser.add_argument(
        "--notes",
        default="",
        help="Optional notes applied to all updated segments.",
    )
    batch_set_parser.set_defaults(func=_handle_review_batch_set)

    compare_list_parser = review_subparsers.add_parser(
        "compare-list",
        help="List OCR comparison candidates across multiple OCR runs.",
    )
    compare_list_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    compare_list_parser.add_argument(
        "--prepare-run",
        help="Prepare run identifier. Defaults to the selected or first available prepare run.",
    )
    compare_list_parser.add_argument(
        "--target-ocr-run",
        required=True,
        help="Target OCR run whose review_state.jsonl will receive chosen winners.",
    )
    compare_list_parser.add_argument(
        "--source-ocr-run",
        action="append",
        default=[],
        help="Source OCR run to include in the comparison. Repeat to include multiple runs.",
    )
    compare_list_parser.add_argument(
        "--segment",
        help="Optional segment_id to limit output to one compared segment.",
    )
    compare_list_parser.set_defaults(func=_handle_review_compare_list)

    compare_apply_parser = review_subparsers.add_parser(
        "compare-apply",
        help="Apply one OCR run's text as the chosen winner for one segment.",
    )
    compare_apply_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    compare_apply_parser.add_argument(
        "--target-ocr-run",
        required=True,
        help="Target OCR run whose review_state.jsonl will be updated.",
    )
    compare_apply_parser.add_argument(
        "--source-ocr-run",
        required=True,
        help="OCR run that provides the chosen text winner.",
    )
    compare_apply_parser.add_argument(
        "--segment",
        required=True,
        help="Segment identifier whose winner should be applied.",
    )
    compare_apply_parser.add_argument(
        "--notes",
        help="Optional notes stored with the chosen compare winner.",
    )
    compare_apply_parser.set_defaults(func=_handle_review_compare_apply)


def _handle_review_list(args: argparse.Namespace) -> int:
    try:
        items = load_review_items(
            Path(args.project),
            prepare_run=args.prepare_run,
            ocr_run=args.ocr_run,
            filter_name=args.filter,
        )
    except (ProjectWorkspaceError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(json.dumps([item.to_dict() for item in items], indent=2))
    return 0


def _handle_review_set(args: argparse.Namespace) -> int:
    try:
        state = save_review_edit(
            Path(args.project),
            ocr_run=args.ocr_run,
            segment_id=args.segment,
            review_status=args.status,
            edited_text=args.text,
            notes=args.notes,
        )
    except (ProjectWorkspaceError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(json.dumps(state.to_dict(), indent=2))
    return 0


def _handle_review_batch_set(args: argparse.Namespace) -> int:
    try:
        states = save_review_batch(
            Path(args.project),
            prepare_run=args.prepare_run,
            ocr_run=args.ocr_run,
            review_status=args.status,
            segment_ids=tuple(args.segment),
            filter_name=args.filter,
            notes=args.notes,
        )
    except (ProjectWorkspaceError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(
        json.dumps(
            {
                "updated_count": len(states),
                "review_status": args.status,
                "segment_ids": [state.segment_id for state in states],
            },
            indent=2,
        )
    )
    return 0


def _handle_review_compare_list(args: argparse.Namespace) -> int:
    try:
        summary = load_ocr_comparison_summary(
            Path(args.project),
            prepare_run=args.prepare_run,
            target_ocr_run=args.target_ocr_run,
            source_ocr_runs=tuple(args.source_ocr_run),
        )
    except ProjectWorkspaceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    items = summary.items
    if args.segment:
        matched_item = find_ocr_comparison_item(summary, args.segment)
        items = () if matched_item is None else (matched_item,)

    print(
        json.dumps(
            {
                "selected_prepare_run": summary.selected_prepare_run,
                "selected_target_ocr_run": summary.selected_target_ocr_run,
                "selected_source_ocr_runs": list(summary.selected_source_ocr_runs),
                "available_ocr_run_options": list(summary.available_ocr_run_options),
                "item_count": len(items),
                "warnings": list(summary.warnings),
                "items": [_serialize_comparison_item(item) for item in items],
            },
            indent=2,
        )
    )
    return 0


def _handle_review_compare_apply(args: argparse.Namespace) -> int:
    try:
        outcome = apply_ocr_comparison_choice(
            Path(args.project),
            target_ocr_run=args.target_ocr_run,
            source_ocr_run=args.source_ocr_run,
            segment_id=args.segment,
            notes=args.notes,
        )
    except ProjectWorkspaceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(
        json.dumps(
            {
                "target_ocr_run": outcome.target_ocr_run,
                "source_ocr_run": outcome.source_ocr_run,
                "segment_id": outcome.segment_id,
                "chosen_text": outcome.chosen_text,
                "review_status": outcome.review_status,
                "review_state_path": str(outcome.review_state_path),
            },
            indent=2,
        )
    )
    return 0


def _serialize_comparison_item(item) -> dict[str, object]:
    return {
        "segment_id": item.segment_id,
        "zone_idx": item.zone_idx,
        "start_ms": item.start_ms,
        "end_ms": item.end_ms,
        "time_label": item.time_label,
        "representative_image_path": str(item.representative_image_path),
        "target_review_status": item.target_review_status,
        "target_edited_text": item.target_edited_text,
        "target_effective_text": item.target_effective_text,
        "candidates": [
            {
                "run_id": candidate.run_id,
                "backend_name": candidate.backend_name,
                "model_name": candidate.model_name,
                "text": candidate.text,
                "status": candidate.status,
                "error": candidate.error,
            }
            for candidate in item.candidates
        ],
    }
