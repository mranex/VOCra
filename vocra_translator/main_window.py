from __future__ import annotations
import os
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vocra_translator.core.app_config import load_global_config, save_global_config
from vocra_translator.core.format_utils import format_display_timestamp
from vocra_translator.core.project_store import create_project_from_subtitle, load_project, save_project
from vocra_translator.core.translation_service import apply_translation_cache, build_translation_signature, load_translation_cache, save_translation_cache
from vocra_translator.scenes.config_scene import ConfigScene
from vocra_translator.scenes.export_scene import ExportScene
from vocra_translator.scenes.project_scene import ProjectScene
from vocra_translator.scenes.translate_scene import TranslateScene
from vocra_translator.widgets.scene_nav_button import SceneNavButton


class VoCRATranslatorMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoCRA Translator")
        self.resize(1500, 940)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))


        self.project_dir: str | None = None
        self.manifest: dict | None = None
        self.document = None
        self.global_config = load_global_config()

        self.stack = QStackedWidget()
        self.sidebar_buttons: list[QToolButton] = []

        self.scene_project = ProjectScene(self)
        self.scene_translate = TranslateScene(self)
        self.scene_export = ExportScene(self)
        self.scene_config = ConfigScene(self)

        self.scenes = [
            self.scene_project,
            self.scene_translate,
            self.scene_export,
            self.scene_config,
        ]
        for scene in self.scenes:
            self.stack.addWidget(scene)

        self._build_ui()
        self.set_active_scene(0)
        self.refresh_all_scenes()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootWidget")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_nav = QFrame()
        top_nav.setObjectName("TopNav")
        top_nav_layout = QHBoxLayout(top_nav)
        top_nav_layout.setContentsMargins(18, 14, 18, 10)
        top_nav_layout.setSpacing(0)

        for index, label in enumerate(["Project", "Translate", "Export", "Config"]):
            button = SceneNavButton(label)
            button.setProperty("nav", True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, idx=index: self.set_active_scene(idx))
            top_nav_layout.addWidget(button, 1)
            self.sidebar_buttons.append(button)

        layout.addWidget(top_nav)
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

    def import_subtitle_file(self, subtitle_path: str) -> None:
        try:
            manifest, document = create_project_from_subtitle(subtitle_path, global_config=self.global_config)
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))
            return
        self.project_dir = manifest["project_dir"]
        self.manifest = manifest
        self.document = document
        self.refresh_all_scenes()
        self.set_active_scene(1)
        QMessageBox.information(self, "Project Created", f"Translator project ready at:\n{self.project_dir}")

    def load_project(self, project_dir: str) -> None:
        try:
            manifest, document = load_project(project_dir, global_config=self.global_config)
            signature = build_translation_signature(manifest, document)
            cache_payload = load_translation_cache(project_dir)
            apply_translation_cache(document, cache_payload, signature)
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", str(exc))
            return
        self.project_dir = str(Path(project_dir).expanduser().resolve())
        self.manifest = manifest
        self.document = document
        self.refresh_all_scenes()

    def reload_current_project(self) -> None:
        if self.project_dir:
            self.load_project(self.project_dir)

    def save_global_app_config(self, config: dict) -> None:
        save_global_config(config)
        self.global_config = load_global_config()
        self.scene_config.refresh_from_config(self.global_config)

    def save_project_translation_settings(self, translator: dict, context: str) -> None:
        if not self.project_dir or not self.manifest or self.document is None:
            return
        merged = dict(self.manifest.get("translator", {}))
        merged.update(translator)
        self.manifest["translator"] = merged
        self.manifest["context"] = str(context or "")
        api_key = str(merged.get("api_key", "") or "")
        if api_key and api_key != str(self.global_config.get("translator", {}).get("api_key", "") or ""):
            next_config = {"translator": dict(self.global_config.get("translator", {}))}
            next_config["translator"]["api_key"] = api_key
            save_global_config(next_config)
            self.global_config = load_global_config()
            self.manifest["translator"]["api_key"] = api_key
        save_project(self.project_dir, self.manifest, self.document)

    def save_translation_edits(self, edits: list[dict]) -> None:
        if not edits or not self.project_dir or not self.manifest or self.document is None:
            return
        entries_by_id = {entry.id: entry for entry in self.document.entries}
        for item in edits:
            entry_id = int(item.get("entry_id", 0) or 0)
            entry = entries_by_id.get(entry_id)
            if entry is None:
                continue
            entry.translation_text = str(item.get("translation_text", "") or "")
            entry.edited = True
            entry.status = "done" if entry.translation_text else "pending"
        save_project(self.project_dir, self.manifest, self.document)
        cache_payload = load_translation_cache(self.project_dir)
        signature = cache_payload.get("signature") or build_translation_signature(self.manifest, self.document)
        save_translation_cache(self.project_dir, self.document, signature)
        self.refresh_all_scenes()

    def refresh_all_scenes(self) -> None:
        table_entries = self._table_entries()
        self.scene_project.refresh_from_project(self.project_dir, self.manifest, table_entries)
        self.scene_translate.refresh_from_project(self.project_dir, self.manifest, table_entries)
        self.scene_export.refresh_from_project(self.project_dir, self.manifest, table_entries)
        self.scene_config.refresh_from_config(self.global_config)

    def _table_entries(self) -> list[dict]:
        if self.document is None:
            return []
        entries = []
        for index, entry in enumerate(self.document.entries, start=1):
            labels = []
            if entry.translation_text:
                labels.append("translated")
            if entry.edited:
                labels.append("edited")
            if entry.stale:
                labels.append("stale")
            if not labels:
                labels.append(entry.status)
            entries.append(
                {
                    "index": index,
                    "entry_id": entry.id,
                    "start": format_display_timestamp(entry.start_ms),
                    "end": format_display_timestamp(entry.end_ms),
                    "source_text": entry.source_text,
                    "translation_text": entry.translation_text,
                    "edited": entry.edited,
                    "stale": entry.stale,
                    "status_label": ", ".join(label for label in labels if label),
                }
            )
        return entries


def load_qss() -> str:
    qss_path = Path(__file__).resolve().parent / "styles" / "theme.qss"
    return qss_path.read_text(encoding="utf-8")


def run_app(argv) -> int:
    app = QApplication(argv)
    app.setStyleSheet(load_qss())
    window = VoCRATranslatorMainWindow()
    window.show()
    return app.exec()
