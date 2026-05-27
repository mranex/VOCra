from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vocra_translator.core.project_store import create_project_from_subtitle
from vocra_translator.core.translation_service import (
    apply_translation_cache,
    build_translation_signature,
    load_translation_cache,
    save_translation_cache,
)


class TranslationCacheTests(unittest.TestCase):
    def test_signature_changes_with_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subtitle = Path(tmp) / "sample.srt"
            subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
            manifest, document = create_project_from_subtitle(str(subtitle), global_config={"translator": {}}, projects_root=tmp)
            signature_a = build_translation_signature(manifest, document)
            manifest["context"] = "Comedy scene"
            signature_b = build_translation_signature(manifest, document)
            self.assertNotEqual(signature_a, signature_b)

    def test_stale_cache_is_loaded_but_marked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subtitle = Path(tmp) / "sample.srt"
            subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
            manifest, document = create_project_from_subtitle(str(subtitle), global_config={"translator": {}}, projects_root=tmp)
            signature = build_translation_signature(manifest, document)
            document.entries[0].translation_text = "Xin chao"
            document.entries[0].status = "done"
            save_translation_cache(manifest["project_dir"], document, signature)

            stale_signature = dict(signature)
            stale_signature["context"] = "Changed"
            cache_payload = load_translation_cache(manifest["project_dir"])
            matches = apply_translation_cache(document, cache_payload, stale_signature)
            self.assertFalse(matches)
            self.assertEqual("Xin chao", document.entries[0].translation_text)
            self.assertTrue(document.entries[0].stale)


if __name__ == "__main__":
    unittest.main()
