"""Project-tab widgets for the VOCra GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import PySimpleGUI as sg

from vocra.app.models import ProjectDashboard, RecentProjectSummary
from vocra.app.service import render_project_overview_text, render_stage_status_text

CREATE_VIDEO_KEY = "-CREATE-VIDEO-"
CREATE_PROJECT_PATH_KEY = "-CREATE-PROJECT-PATH-"
CREATE_PROJECT_BUTTON_KEY = "-CREATE-PROJECT-"
PROJECT_INFO_KEY = "-PROJECT-INFO-"
ARTIFACT_STATUS_KEY = "-ARTIFACT-STATUS-"
RECENT_PROJECTS_KEY = "-RECENT-PROJECTS-"


def build_project_tab() -> list[list[Any]]:
    return [
        [
            sg.Frame(
                "Create Project",
                [
                    [
                        sg.Text("Source video"),
                        sg.Input("", key=CREATE_VIDEO_KEY, expand_x=True),
                        sg.FileBrowse(target=CREATE_VIDEO_KEY),
                    ],
                    [
                        sg.Text("Project folder"),
                        sg.Input("", key=CREATE_PROJECT_PATH_KEY, expand_x=True),
                        sg.FolderBrowse(target=CREATE_PROJECT_PATH_KEY),
                    ],
                    [sg.Button("Create Project", key=CREATE_PROJECT_BUTTON_KEY)],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Recent Projects",
                [
                    [
                        sg.Listbox(
                            values=[],
                            key=RECENT_PROJECTS_KEY,
                            size=(40, 6),
                            expand_x=True,
                        )
                    ],
                    [sg.Button("Open Selected Recent", key="-OPEN-RECENT-PROJECT-")],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Project Overview",
                [
                    [
                        sg.Multiline(
                            "",
                            key=PROJECT_INFO_KEY,
                            expand_x=True,
                            expand_y=True,
                            disabled=True,
                            size=(60, 10),
                        )
                    ]
                ],
                expand_x=True,
                expand_y=True,
            ),
            sg.Frame(
                "Artifact Status",
                [
                    [
                        sg.Multiline(
                            "",
                            key=ARTIFACT_STATUS_KEY,
                            expand_x=True,
                            expand_y=True,
                            disabled=True,
                            size=(60, 10),
                        )
                    ]
                ],
                expand_x=True,
                expand_y=True,
            ),
        ],
    ]


def set_empty_project_tab(window: sg.Window) -> None:
    window[PROJECT_INFO_KEY].update(
        "Create a new .vocra project or open an existing one to view source metadata."
    )
    window[ARTIFACT_STATUS_KEY].update(
        "Artifact status will appear here after a project is loaded."
    )


def update_project_tab(window: sg.Window, dashboard: ProjectDashboard) -> None:
    window[PROJECT_INFO_KEY].update(render_project_overview_text(dashboard))
    window[ARTIFACT_STATUS_KEY].update(render_stage_status_text(dashboard))


def update_recent_projects(
    window: sg.Window,
    recent_projects: tuple[RecentProjectSummary, ...],
) -> None:
    window[RECENT_PROJECTS_KEY].update(
        values=[_format_recent_project(entry) for entry in recent_projects]
    )


def parse_recent_project_selection(values: dict[str, object]) -> Path | None:
    selected = values.get(RECENT_PROJECTS_KEY)
    if not isinstance(selected, list) or not selected:
        return None
    raw_value = str(selected[0])
    if " | " not in raw_value:
        return None
    _, project_root = raw_value.split(" | ", maxsplit=1)
    return Path(project_root)


def _format_recent_project(entry: RecentProjectSummary) -> str:
    return f"{entry.project_name} | {entry.project_root}"
