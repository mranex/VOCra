from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vocra_core.burner import DEFAULT_BURN_STYLE, build_default_output_path, normalize_burn_style, run_burn_video
from vocra_core.exporter import _build_export_entries
from vocra_core.project_manager import load_project, save_progress
from vocra_core.timestamp_utils import timestamp_to_millis
from vocra_gui.widgets.video_preview import VideoPreview
from vocra_gui.workers import TaskWorker


ALIGNMENT_OPTIONS = [
    ("Top Left", "top_left"),
    ("Top Center", "top_center"),
    ("Top Right", "top_right"),
    ("Middle Left", "middle_left"),
    ("Middle Center", "middle_center"),
    ("Middle Right", "middle_right"),
    ("Bottom Left", "bottom_left"),
    ("Bottom Center", "bottom_center"),
    ("Bottom Right", "bottom_right"),
]


class BurnScene(QWidget):
    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self._burn_worker: TaskWorker | None = None
        self._project_dir: str | None = None
        self._output_project_dir: str | None = None
        self._source_project_dir: str | None = None
        self._settings_project_dir: str | None = None
        self._loading_settings = False
        self._settings_dirty = False
        self._entries: list[dict] = []

        self.video_preview = VideoPreview(self)
        self.preview_overlay = BurnPreviewOverlay(self.video_preview.video_widget)
        self.preview_overlay.raise_()

        self.source_combo = QComboBox()
        self.output_edit = QLineEdit()
        self.output_browse_button = QPushButton("Browse")
        self.encoder_label = QLabel("Encoder: preserve codec with NVENC, fallback H.264 NVENC")
        self.encoder_label.setProperty("muted", True)

        self.blur_check = QCheckBox("Blur original subtitle region")
        self.blur_strength_spin = QSpinBox()
        self.blur_strength_spin.setRange(1, 64)

        self.position_mode_combo = QComboBox()
        self.position_mode_combo.addItem("Screen preset", "screen")
        self.position_mode_combo.addItem("Crop stamp", "crop_stamp")
        self.alignment_combo = QComboBox()
        for label, value in ALIGNMENT_OPTIONS:
            self.alignment_combo.addItem(label, value)

        self.font_combo = QFontComboBox()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 160)
        self.bold_check = QCheckBox("Bold")
        self.italic_check = QCheckBox("Italic")
        self.primary_color_edit = QLineEdit()
        self.outline_color_edit = QLineEdit()
        self.shadow_color_edit = QLineEdit()
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.outline_width_spin = QSpinBox()
        self.outline_width_spin.setRange(0, 20)
        self.shadow_depth_spin = QSpinBox()
        self.shadow_depth_spin.setRange(0, 20)
        self.margin_l_spin = QSpinBox()
        self.margin_l_spin.setRange(0, 1000)
        self.margin_r_spin = QSpinBox()
        self.margin_r_spin.setRange(0, 1000)
        self.margin_v_spin = QSpinBox()
        self.margin_v_spin.setRange(0, 1000)
        self.max_line_chars_spin = QSpinBox()
        self.max_line_chars_spin.setRange(8, 120)

        self.save_default_button = QPushButton("Save as Default")
        self.burn_button = QPushButton("Burn Video")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.status_label = QLabel("Open or create a processed project to burn video.")
        self.status_label.setWordWrap(True)

        self._build_ui()
        self._connect_signals()

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self._update_preview_from_position)
        self._preview_timer.start()

    def _build_ui(self) -> None:
        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        source_card = QFrame()
        source_card.setObjectName("Card")
        source_layout = QFormLayout(source_card)
        source_layout.setContentsMargins(16, 16, 16, 16)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_browse_button)
        source_layout.addRow("Subtitle Source", self.source_combo)
        source_layout.addRow("Output MP4", output_row)
        source_layout.addRow(self.encoder_label)
        settings_layout.addWidget(_with_title("Burn Output", source_card))

        effect_card = QFrame()
        effect_card.setObjectName("Card")
        effect_layout = QFormLayout(effect_card)
        effect_layout.setContentsMargins(16, 16, 16, 16)
        effect_layout.addRow("Original Subtitle", self.blur_check)
        effect_layout.addRow("Blur Strength", self.blur_strength_spin)
        effect_layout.addRow("Position Mode", self.position_mode_combo)
        effect_layout.addRow("Screen Position", self.alignment_combo)
        settings_layout.addWidget(_with_title("Position + Blur", effect_card))

        style_card = QFrame()
        style_card.setObjectName("Card")
        style_layout = QGridLayout(style_card)
        style_layout.setContentsMargins(16, 16, 16, 16)
        style_layout.setHorizontalSpacing(10)
        style_layout.setVerticalSpacing(8)

        style_layout.addWidget(QLabel("Font"), 0, 0)
        style_layout.addWidget(self.font_combo, 0, 1, 1, 3)
        style_layout.addWidget(QLabel("Size"), 1, 0)
        style_layout.addWidget(self.font_size_spin, 1, 1)
        style_layout.addWidget(self.bold_check, 1, 2)
        style_layout.addWidget(self.italic_check, 1, 3)
        self._add_color_row(style_layout, 2, "Text", self.primary_color_edit)
        self._add_color_row(style_layout, 3, "Outline", self.outline_color_edit)
        self._add_color_row(style_layout, 4, "Shadow", self.shadow_color_edit)
        style_layout.addWidget(QLabel("Opacity"), 5, 0)
        style_layout.addWidget(self.opacity_spin, 5, 1)
        style_layout.addWidget(QLabel("Outline"), 5, 2)
        style_layout.addWidget(self.outline_width_spin, 5, 3)
        style_layout.addWidget(QLabel("Shadow"), 6, 0)
        style_layout.addWidget(self.shadow_depth_spin, 6, 1)
        style_layout.addWidget(QLabel("Wrap"), 6, 2)
        style_layout.addWidget(self.max_line_chars_spin, 6, 3)
        style_layout.addWidget(QLabel("Margin L"), 7, 0)
        style_layout.addWidget(self.margin_l_spin, 7, 1)
        style_layout.addWidget(QLabel("Margin R"), 7, 2)
        style_layout.addWidget(self.margin_r_spin, 7, 3)
        style_layout.addWidget(QLabel("Margin V"), 8, 0)
        style_layout.addWidget(self.margin_v_spin, 8, 1)
        settings_layout.addWidget(_with_title("Subtitle Style", style_card))

        action_card = QFrame()
        action_card.setObjectName("Card")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_row = QHBoxLayout()
        action_row.addWidget(self.save_default_button)
        action_row.addStretch(1)
        action_row.addWidget(self.burn_button)
        action_row.addWidget(self.cancel_button)
        action_layout.addWidget(self.progress_bar)
        action_layout.addLayout(action_row)
        action_layout.addWidget(self.status_label)
        settings_layout.addWidget(action_card)
        settings_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(settings_panel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self.video_preview, 2)
        layout.addWidget(scroll, 1)

    def _add_color_row(self, layout: QGridLayout, row: int, label: str, edit: QLineEdit) -> None:
        button = QPushButton("Pick")
        button.clicked.connect(lambda checked=False, target=edit: self._pick_color(target))
        layout.addWidget(QLabel(label), row, 0)
        layout.addWidget(edit, row, 1, 1, 2)
        layout.addWidget(button, row, 3)

    def _connect_signals(self) -> None:
        self.output_browse_button.clicked.connect(self.browse_output)
        self.source_combo.currentIndexChanged.connect(self.reload_entries)
        self.position_mode_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.alignment_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.font_combo.currentFontChanged.connect(lambda _font: self._on_setting_changed())
        for widget in (
            self.blur_check,
            self.bold_check,
            self.italic_check,
        ):
            widget.toggled.connect(self._on_setting_changed)
        for widget in (
            self.blur_strength_spin,
            self.font_size_spin,
            self.opacity_spin,
            self.outline_width_spin,
            self.shadow_depth_spin,
            self.margin_l_spin,
            self.margin_r_spin,
            self.margin_v_spin,
            self.max_line_chars_spin,
        ):
            widget.valueChanged.connect(self._on_setting_changed)
        for edit in (self.primary_color_edit, self.outline_color_edit, self.shadow_color_edit):
            edit.textChanged.connect(self._on_setting_changed)
        self.video_preview.video_widget.installEventFilter(self)
        self.video_preview.display_frame.installEventFilter(self)
        self.video_preview.seek_slider.valueChanged.connect(self._update_preview_from_position)
        self.burn_button.clicked.connect(self.burn_video)
        self.cancel_button.clicked.connect(self.cancel_burn)
        self.save_default_button.clicked.connect(self.save_as_default)

    def eventFilter(self, watched, event) -> bool:
        if watched in (self.video_preview.video_widget, self.video_preview.display_frame):
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._sync_overlay_geometry()
        return super().eventFilter(watched, event)

    def refresh_from_project(self, project_dir: str | None, progress: dict | None) -> None:
        enabled = bool(project_dir and progress and progress.get("status", {}).get("segments_done"))
        self._project_dir = project_dir if enabled else None
        self._set_controls_enabled(enabled and not self._is_running())
        self.cancel_button.setEnabled(self._is_running())
        if not enabled:
            self._entries = []
            self.video_preview.close_source()
            self.preview_overlay.set_payload("", {}, {}, (0, 0))
            self.status_label.setText("Open or create a processed project to burn video.")
            return

        assert project_dir is not None and progress is not None
        video_path = str(progress.get("video_path", "") or "")
        if video_path and Path(video_path).exists() and self.video_preview.source_path() != str(Path(video_path).resolve()):
            self.video_preview.set_source(video_path)
            self._sync_overlay_geometry()

        if self._settings_project_dir != project_dir or not self._settings_dirty:
            self._load_settings(progress)
            self._settings_project_dir = project_dir
        self._load_sources(progress)
        if self._output_project_dir != project_dir:
            burn = progress.get("burn_video", {}) or {}
            self.output_edit.setText(str(burn.get("last_output_path") or build_default_output_path(project_dir, progress)))
            self._output_project_dir = project_dir
        elif not self.output_edit.text().strip():
            self.output_edit.setText(build_default_output_path(project_dir, progress))
        self.reload_entries()
        self.status_label.setText("Ready")

    def _load_settings(self, progress: dict) -> None:
        self._loading_settings = True
        burn = progress.get("burn_video", {}) or {}
        try:
            self.blur_check.setChecked(bool(burn.get("last_blur_enabled", burn.get("blur_enabled", True))))
            self.blur_strength_spin.setValue(int(burn.get("last_blur_strength", burn.get("blur_strength", 8)) or 8))
            style = normalize_burn_style(burn.get("last_burn_style") or burn.get("burn_style"))
            self.font_combo.setCurrentFont(QFont(str(style["font_family"])))
            self.font_size_spin.setValue(int(style["font_size"]))
            self.bold_check.setChecked(bool(style["bold"]))
            self.italic_check.setChecked(bool(style["italic"]))
            self.primary_color_edit.setText(str(style["primary_color"]))
            self.outline_color_edit.setText(str(style["outline_color"]))
            self.shadow_color_edit.setText(str(style["shadow_color"]))
            self.opacity_spin.setValue(int(style["opacity"]))
            self.outline_width_spin.setValue(int(style["outline_width"]))
            self.shadow_depth_spin.setValue(int(style["shadow_depth"]))
            self._set_combo_data(self.alignment_combo, str(style["alignment"]))
            self.margin_l_spin.setValue(int(style["margin_l"]))
            self.margin_r_spin.setValue(int(style["margin_r"]))
            self.margin_v_spin.setValue(int(style["margin_v"]))
            self.max_line_chars_spin.setValue(int(style["max_line_chars"]))
            self._set_combo_data(self.position_mode_combo, str(style["position_mode"]))
        finally:
            self._loading_settings = False
            self._settings_dirty = False

    def _load_sources(self, progress: dict) -> None:
        current = self.source_combo.currentData()
        project_changed = self._source_project_dir != self._project_dir
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        status = progress.get("status", {})
        project_path = Path(str(self._project_dir or ""))
        cache_files = progress.get("cache_files", {})
        translation_path = project_path / str(cache_files.get("translation", "cache/translation.json"))
        if status.get("ocr_final_done"):
            self.source_combo.addItem("Original OCR", "final_ocr")
        if status.get("segments_done"):
            self.source_combo.addItem("Draft Voted Text", "draft_voted")
        if translation_path.exists():
            self.source_combo.addItem("Translation", "translation")
        preferred = "translation" if self.source_combo.findData("translation") >= 0 else "draft_voted"
        selected = preferred if project_changed else current
        if self.source_combo.findData(selected) < 0:
            selected = preferred
        self._set_combo_data(self.source_combo, selected)
        self._source_project_dir = self._project_dir
        self.source_combo.blockSignals(False)

    def reload_entries(self) -> None:
        if not self._project_dir or self.source_combo.count() <= 0:
            self._entries = []
            self._update_preview_from_position()
            return
        try:
            self._entries = _build_export_entries(self._project_dir, export_source=str(self.source_combo.currentData()))
        except Exception as exc:
            self._entries = []
            self.status_label.setText(str(exc))
        self._update_preview_from_position()

    def browse_output(self) -> None:
        if not self._project_dir:
            return
        current = self.output_edit.text().strip() or build_default_output_path(self._project_dir, self.main_window.progress)
        output_path, _filter = QFileDialog.getSaveFileName(self, "Burn Video", str(Path(current).with_suffix(".mp4")), "MP4 Video (*.mp4)")
        if output_path:
            self.output_edit.setText(str(Path(output_path).with_suffix(".mp4")))

    def burn_video(self) -> None:
        if not self._project_dir:
            return
        self._commit_spinbox_edits()
        progress = load_project(self._project_dir)
        burn_config = progress.get("burn_video", {})
        output_path = self.output_edit.text().strip() or build_default_output_path(self._project_dir, progress)
        if Path(output_path).suffix.lower() != ".mp4":
            output_path = str(Path(output_path).with_suffix(".mp4"))
            self.output_edit.setText(output_path)
        style = self._style_from_form()
        self._save_project_burn_settings(progress, output_path=output_path, style=style)

        self.progress_bar.setValue(0)
        self.status_label.setText("Starting FFmpeg burn...")
        self._set_controls_enabled(False)
        self.cancel_button.setEnabled(True)
        self._burn_worker = TaskWorker(
            lambda callback: run_burn_video(
                self._project_dir,
                output_path=output_path,
                export_source=str(self.source_combo.currentData() or "draft_voted"),
                ffmpeg_path=str(burn_config.get("ffmpeg_path", "") or ""),
                blur_enabled=self.blur_check.isChecked(),
                blur_strength=int(self.blur_strength_spin.value()),
                burn_style=style,
                callback=callback,
            ),
            self,
        )
        self._burn_worker.progress.connect(self._on_burn_progress)
        self._burn_worker.finished_with_status.connect(self._on_burn_finished)
        self._burn_worker.start()

    def cancel_burn(self) -> None:
        if self._is_running():
            self.status_label.setText("Cancelling burn...")
            self._burn_worker.requestInterruption()

    def save_as_default(self) -> None:
        self._commit_spinbox_edits()
        style = self._style_from_form()
        if self._project_dir:
            progress = load_project(self._project_dir)
            self._save_project_burn_settings(
                progress,
                output_path=self.output_edit.text().strip() or build_default_output_path(self._project_dir, progress),
                style=style,
            )
        config = dict(self.main_window.global_config)
        burn = dict(config.get("burn_video", {}) or {})
        burn["blur_enabled"] = self.blur_check.isChecked()
        burn["blur_strength"] = int(self.blur_strength_spin.value())
        burn["burn_style"] = style
        config["burn_video"] = burn
        self.main_window.save_global_app_config(config)
        self._settings_dirty = False
        QMessageBox.information(self, "Saved", "Burn style saved as the global default.")

    def _save_project_burn_settings(self, progress: dict, *, output_path: str, style: dict) -> None:
        burn = progress.setdefault("burn_video", {})
        burn["blur_enabled"] = self.blur_check.isChecked()
        burn["blur_strength"] = int(self.blur_strength_spin.value())
        burn["burn_style"] = style
        burn["last_output_path"] = output_path
        burn["last_export_source"] = str(self.source_combo.currentData() or "draft_voted")
        burn["last_blur_enabled"] = self.blur_check.isChecked()
        burn["last_blur_strength"] = int(self.blur_strength_spin.value())
        burn["last_burn_style"] = style
        save_progress(self._project_dir, progress)
        self._remember_project_progress(progress)
        self._settings_dirty = False

    def _on_burn_progress(self, current: int, total: int, message: str) -> None:
        percent = int(current * 100 / max(total, 1))
        self.progress_bar.setValue(max(0, min(100, percent)))
        if message:
            self.status_label.setText(message)

    def _on_burn_finished(self, success: bool, message: str) -> None:
        self._set_controls_enabled(bool(self._project_dir))
        self.cancel_button.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            self.main_window.reload_current_project()
            QMessageBox.information(self, "Burn Complete", f"Video exported to:\n{self.output_edit.text().strip()}")
        else:
            self.status_label.setText(message or "Burn failed.")
            QMessageBox.critical(self, "Burn Failed", message or "Burn failed.")

    def _style_from_form(self) -> dict:
        return normalize_burn_style(
            {
                "font_family": self.font_combo.currentFont().family(),
                "font_size": int(self.font_size_spin.value()),
                "bold": self.bold_check.isChecked(),
                "italic": self.italic_check.isChecked(),
                "primary_color": self.primary_color_edit.text().strip(),
                "outline_color": self.outline_color_edit.text().strip(),
                "shadow_color": self.shadow_color_edit.text().strip(),
                "opacity": int(self.opacity_spin.value()),
                "outline_width": int(self.outline_width_spin.value()),
                "shadow_depth": int(self.shadow_depth_spin.value()),
                "alignment": str(self.alignment_combo.currentData() or "bottom_center"),
                "margin_l": int(self.margin_l_spin.value()),
                "margin_r": int(self.margin_r_spin.value()),
                "margin_v": int(self.margin_v_spin.value()),
                "max_line_chars": int(self.max_line_chars_spin.value()),
                "position_mode": str(self.position_mode_combo.currentData() or "screen"),
            }
        )

    def _on_setting_changed(self, *args) -> None:
        del args
        if not self._loading_settings:
            self._settings_dirty = True
        self._update_preview_from_position()

    def _commit_spinbox_edits(self) -> None:
        for widget in (
            self.blur_strength_spin,
            self.font_size_spin,
            self.opacity_spin,
            self.outline_width_spin,
            self.shadow_depth_spin,
            self.margin_l_spin,
            self.margin_r_spin,
            self.margin_v_spin,
            self.max_line_chars_spin,
        ):
            widget.interpretText()

    def _remember_project_progress(self, progress: dict) -> None:
        if getattr(self.main_window, "project_dir", None) == self._project_dir:
            self.main_window.progress = progress

    def _update_preview_from_position(self) -> None:
        crop = {}
        video_size = self.video_preview.video_size()
        if self.main_window.progress:
            crop = self.main_window.progress.get("subtitle_crop", {}) or {}
        text = self._preview_text_for_position(self.video_preview.current_position_ms())
        self.preview_overlay.set_payload(text, self._style_from_form(), crop, video_size)

    def _preview_text_for_position(self, position_ms: int) -> str:
        if not self._entries:
            return "Subtitle preview"
        for entry in self._entries:
            try:
                start = timestamp_to_millis(str(entry.get("start", "00:00:00.000")))
                end = timestamp_to_millis(str(entry.get("end", "00:00:00.000")))
            except Exception:
                continue
            if start <= position_ms <= end:
                return str(entry.get("text", "") or "Subtitle preview")
        return str(self._entries[0].get("text", "") or "Subtitle preview")

    def _sync_overlay_geometry(self) -> None:
        target = self.video_preview.video_widget.geometry()
        self.preview_overlay.setGeometry(QRect(0, 0, target.width(), target.height()))
        self.preview_overlay.raise_()
        self._update_preview_from_position()

    def _pick_color(self, edit: QLineEdit) -> None:
        color = QColorDialog.getColor(QColor(edit.text().strip() or "#FFFFFF"), self, "Select Color")
        if color.isValid():
            edit.setText(color.name().upper())

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.source_combo,
            self.output_edit,
            self.output_browse_button,
            self.blur_check,
            self.blur_strength_spin,
            self.position_mode_combo,
            self.alignment_combo,
            self.font_combo,
            self.font_size_spin,
            self.bold_check,
            self.italic_check,
            self.primary_color_edit,
            self.outline_color_edit,
            self.shadow_color_edit,
            self.opacity_spin,
            self.outline_width_spin,
            self.shadow_depth_spin,
            self.margin_l_spin,
            self.margin_r_spin,
            self.margin_v_spin,
            self.max_line_chars_spin,
            self.save_default_button,
            self.burn_button,
        ):
            widget.setEnabled(enabled)

    def _is_running(self) -> bool:
        return bool(self._burn_worker and self._burn_worker.isRunning())

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


class BurnPreviewOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._text = ""
        self._style = normalize_burn_style(DEFAULT_BURN_STYLE)
        self._crop: dict = {}
        self._video_size = (0, 0)
        self.show()

    def set_payload(self, text: str, style: dict, crop: dict, video_size: tuple[int, int]) -> None:
        self._text = str(text or "")
        self._style = normalize_burn_style(style)
        self._crop = dict(crop or {})
        self._video_size = video_size
        self.update()

    def paintEvent(self, event) -> None:
        del event
        if not self._text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        display = self._display_rect()
        if display.isNull():
            return
        if self._style["position_mode"] == "crop_stamp":
            crop_rect = self._map_from_video(self._crop)
            if not crop_rect.isNull():
                painter.setPen(QPen(QColor("#00f0ff"), 2, Qt.PenStyle.DashLine))
                painter.setBrush(QColor(0, 240, 255, 24))
                painter.drawRect(crop_rect)
                target = crop_rect
            else:
                target = display
            flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
        else:
            target = self._screen_target_rect(display)
            flags = self._alignment_flags() | Qt.TextFlag.TextWordWrap

        font = QFont(str(self._style["font_family"]), int(self._scaled_font_size()))
        font.setBold(bool(self._style["bold"]))
        font.setItalic(bool(self._style["italic"]))
        painter.setFont(font)

        outline_color = QColor(str(self._style["outline_color"]))
        outline_width = max(0, int(self._style["outline_width"]))
        if outline_width > 0:
            offsets = [(-outline_width, 0), (outline_width, 0), (0, -outline_width), (0, outline_width)]
            painter.setPen(outline_color)
            for dx, dy in offsets:
                painter.drawText(target.adjusted(dx, dy, dx, dy), flags, self._text)

        text_color = QColor(str(self._style["primary_color"]))
        text_color.setAlpha(int(255 * int(self._style["opacity"]) / 100))
        painter.setPen(text_color)
        painter.drawText(target, flags, self._text)

    def _display_rect(self) -> QRect:
        width, height = self._video_size
        if width <= 0 or height <= 0:
            return self.rect()
        widget_ratio = self.width() / max(1, self.height())
        video_ratio = width / max(1, height)
        if widget_ratio > video_ratio:
            display_height = self.height()
            display_width = int(display_height * video_ratio)
            x = (self.width() - display_width) // 2
            return QRect(x, 0, display_width, display_height)
        display_width = self.width()
        display_height = int(display_width / max(video_ratio, 1e-6))
        y = (self.height() - display_height) // 2
        return QRect(0, y, display_width, display_height)

    def _map_from_video(self, crop: dict) -> QRect:
        display = self._display_rect()
        video_w, video_h = self._video_size
        if display.width() <= 0 or display.height() <= 0 or video_w <= 0 or video_h <= 0:
            return QRect()
        scale_x = display.width() / video_w
        scale_y = display.height() / video_h
        return QRect(
            int(display.x() + int(crop.get("x", 0) or 0) * scale_x),
            int(display.y() + int(crop.get("y", 0) or 0) * scale_y),
            int(int(crop.get("width", 0) or 0) * scale_x),
            int(int(crop.get("height", 0) or 0) * scale_y),
        )

    def _screen_target_rect(self, display: QRect) -> QRect:
        margin_l = int(self._style["margin_l"] * display.width() / max(1, self._video_size[0] or display.width()))
        margin_r = int(self._style["margin_r"] * display.width() / max(1, self._video_size[0] or display.width()))
        margin_v = int(self._style["margin_v"] * display.height() / max(1, self._video_size[1] or display.height()))
        return display.adjusted(margin_l, margin_v, -margin_r, -margin_v)

    def _alignment_flags(self):
        alignment = str(self._style["alignment"])
        horizontal = Qt.AlignmentFlag.AlignHCenter
        vertical = Qt.AlignmentFlag.AlignBottom
        if alignment.endswith("_left"):
            horizontal = Qt.AlignmentFlag.AlignLeft
        elif alignment.endswith("_right"):
            horizontal = Qt.AlignmentFlag.AlignRight
        if alignment.startswith("top_"):
            vertical = Qt.AlignmentFlag.AlignTop
        elif alignment.startswith("middle_"):
            vertical = Qt.AlignmentFlag.AlignVCenter
        return horizontal | vertical

    def _scaled_font_size(self) -> int:
        video_h = self._video_size[1] or 1080
        display = self._display_rect()
        return max(8, int(int(self._style["font_size"]) * display.height() / max(1, video_h)))


def _with_title(title: str, widget: QWidget) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel(title)
    label.setStyleSheet("font-size: 12pt; font-weight: 700; color: #00bcd4;")
    layout.addWidget(label)
    layout.addWidget(widget)
    return container
