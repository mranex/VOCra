from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vocra_core.app_config import load_global_config, merge_global_config_into_progress, save_global_config
from vocra_core.project_manager import create_project, load_project, save_progress
from vocra_gui.scene_config import ConfigScene
from vocra_gui.scene_export import ExportScene
from vocra_gui.scene_process import ProcessScene
from vocra_gui.scene_setup import SetupScene
from vocra_gui.scene_translator import TranslatorScene


class VoCRAMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoCRA")
        self.resize(1440, 920)
        self.project_dir: str | None = None
        self.progress: dict | None = None
        self.global_config = load_global_config()
        self._startup_prompt_shown = False

        self.stack = QStackedWidget()
        self.sidebar_buttons: list[QToolButton] = []

        self.scene_setup = SetupScene(self)
        self.scene_process = ProcessScene(self)
        self.scene_translator = TranslatorScene(self)
        self.scene_export = ExportScene(self)
        self.scene_config = ConfigScene(self)
        self.scenes = [
            self.scene_setup,
            self.scene_process,
            self.scene_translator,
            self.scene_export,
            self.scene_config,
        ]
        for scene in self.scenes:
            self.stack.addWidget(scene)

        self._build_ui()
        self.set_active_scene(0)
        self.refresh_all_scenes()

        if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            QTimer.singleShot(0, self.show_startup_dialog)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 18)
        sidebar_layout.setSpacing(8)

        labels = ["Setup", "Process", "Translate", "Export", "Config"]
        for index, label in enumerate(labels):
            button = QToolButton()
            button.setText(label)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, idx=index: self.set_active_scene(idx))
            sidebar_layout.addWidget(button)
            self.sidebar_buttons.append(button)
        sidebar_layout.addStretch(1)

        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def set_active_scene(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.sidebar_buttons):
            is_active = button_index == index
            button.setChecked(is_active)
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)

    def show_startup_dialog(self) -> None:
        if self._startup_prompt_shown:
            return
        self._startup_prompt_shown = True
        message = QMessageBox(self)
        message.setWindowTitle("Start VoCRA")
        message.setText("Open a video for a new project, or open an existing project folder.")
        open_video_button = message.addButton("Open Video", QMessageBox.ButtonRole.AcceptRole)
        open_project_button = message.addButton("Open Project", QMessageBox.ButtonRole.ActionRole)
        message.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        message.exec()

        clicked = message.clickedButton()
        if clicked is open_video_button:
            self.set_active_scene(0)
            self.scene_setup.choose_video()
        elif clicked is open_project_button:
            self.open_existing_project()

    def open_existing_project(self) -> None:
        project_dir = QFileDialog.getExistingDirectory(self, "Open Project Folder", str(Path.cwd()))
        if project_dir:
            self.load_project(project_dir)

    def create_project(self, *, video_path: str, project_dir: str, subtitle_crop: dict, frame_interval: float) -> None:
        try:
            progress = create_project(video_path, project_dir, subtitle_crop, frame_interval)
            progress = self._sync_global_config_to_project(project_dir, progress=progress)
        except Exception as exc:
            QMessageBox.critical(self, "Create Project Failed", str(exc))
            return
        self.project_dir = str(Path(project_dir).expanduser().resolve())
        self.progress = progress
        self.refresh_all_scenes()
        self.set_active_scene(1)
        QMessageBox.information(self, "Project Created", f"Project ready at:\n{self.project_dir}")

    def load_project(self, project_dir: str) -> None:
        try:
            progress = load_project(project_dir)
            progress = self._sync_global_config_to_project(project_dir, progress=progress)
        except Exception as exc:
            QMessageBox.critical(self, "Load Project Failed", str(exc))
            return
        self.project_dir = str(Path(project_dir).expanduser().resolve())
        self.progress = progress
        self.refresh_all_scenes()

    def reload_current_project(self) -> None:
        if self.project_dir:
            self.load_project(self.project_dir)

    def refresh_all_scenes(self) -> None:
        for scene in self.scenes:
            if hasattr(scene, "refresh_from_project"):
                scene.refresh_from_project(self.project_dir, self.progress)

    def save_global_app_config(self, config: dict) -> None:
        save_global_config(config)
        self.global_config = load_global_config()
        if self.project_dir is not None:
            self.progress = self._sync_global_config_to_project(self.project_dir, progress=self.progress)
        self.refresh_all_scenes()

    def _sync_global_config_to_project(self, project_dir: str, progress: dict | None = None) -> dict:
        project_progress = progress if progress is not None else load_project(project_dir)
        merged_progress = merge_global_config_into_progress(project_progress, self.global_config)
        save_progress(project_dir, merged_progress)
        return merged_progress


def load_qss() -> str:
    qss_path = Path(__file__).resolve().parent / "styles" / "theme.qss"
    return qss_path.read_text(encoding="utf-8")


def run_app(argv) -> int:
    app = QApplication(argv)
    app.setStyleSheet(load_qss())
    window = VoCRAMainWindow()
    window.show()
    return app.exec()
