from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vocra_translator.core.format_registry import load_subtitle_document, save_subtitle_document


class SubtitleFormatTests(unittest.TestCase):
    def test_srt_roundtrip(self) -> None:
        sample = "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:02,500",
                "Hello",
                "",
                "2",
                "00:00:03,000 --> 00:00:04,000",
                "Second line",
                "",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.srt"
            output = Path(tmp) / "out.srt"
            source.write_text(sample, encoding="utf-8")
            document = load_subtitle_document(str(source))
            self.assertEqual(2, len(document.entries))
            document.entries[0].translation_text = "Xin chao"
            save_subtitle_document(document, str(output), target_format="srt", text_source="translation")
            saved = output.read_text(encoding="utf-8")
            self.assertIn("Xin chao", saved)
            self.assertIn("00:00:01,000 --> 00:00:02,500", saved)

    def test_vtt_preserves_note_blocks(self) -> None:
        sample = "\n".join(
            [
                "WEBVTT",
                "",
                "NOTE intro",
                "keep this",
                "",
                "cue-1",
                "00:00:01.000 --> 00:00:02.000 line:90%",
                "Hello VTT",
                "",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.vtt"
            output = Path(tmp) / "out.vtt"
            source.write_text(sample, encoding="utf-8")
            document = load_subtitle_document(str(source))
            document.entries[0].translation_text = "Xin chao VTT"
            save_subtitle_document(document, str(output), target_format="vtt", text_source="translation")
            saved = output.read_text(encoding="utf-8")
            self.assertIn("NOTE intro", saved)
            self.assertIn("line:90%", saved)
            self.assertIn("Xin chao VTT", saved)

    def test_ass_preserves_tags_and_line_breaks(self) -> None:
        sample = "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                "Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1",
                "",
                "[Events]",
                "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
                r"Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\i1}Hello{\i0}\NWorld",
                "",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.ass"
            output = Path(tmp) / "out.ass"
            source.write_text(sample, encoding="utf-8")
            document = load_subtitle_document(str(source))
            self.assertEqual("Hello\nWorld", document.entries[0].source_text)
            document.entries[0].translation_text = "Xin chao\nThe gioi"
            save_subtitle_document(document, str(output), target_format="ass", text_source="translation")
            saved = output.read_text(encoding="utf-8")
            self.assertIn(r"{\i1}", saved)
            self.assertIn(r"{\i0}", saved)
            self.assertIn(r"\N", saved)
            self.assertIn("Xin", saved)

    def test_convert_srt_to_ass(self) -> None:
        sample = "\n".join(
            [
                "1",
                "00:00:01,000 --> 00:00:02,000",
                "Hello convert",
                "",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.srt"
            output = Path(tmp) / "out.ass"
            source.write_text(sample, encoding="utf-8")
            document = load_subtitle_document(str(source))
            document.entries[0].translation_text = "Converted"
            save_subtitle_document(document, str(output), target_format="ass", text_source="translation")
            saved = output.read_text(encoding="utf-8")
            self.assertIn("[Events]", saved)
            self.assertIn("Converted", saved)


if __name__ == "__main__":
    unittest.main()
