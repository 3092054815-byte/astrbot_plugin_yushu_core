from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.memory_store import MemoryStore
from core.memory_types import (
    memory_type_display,
    memory_type_help_text,
    normalize_memory_type,
)


class MemoryTypesTest(unittest.TestCase):
    def test_normalize_memory_type_accepts_chinese_aliases_and_english(self) -> None:
        self.assertEqual(normalize_memory_type("偏好"), "preference")
        self.assertEqual(normalize_memory_type("preference"), "preference")
        self.assertEqual(normalize_memory_type("练习目标"), "skill_goal")
        self.assertEqual(normalize_memory_type("个人资料"), "profile")
        self.assertEqual(normalize_memory_type("资料"), "profile")
        self.assertEqual(normalize_memory_type("个人信息"), "profile")
        self.assertEqual(normalize_memory_type("群聊规则"), "group_rule")
        self.assertEqual(normalize_memory_type("不存在"), None)

    def test_memory_type_display_and_help_are_chinese(self) -> None:
        self.assertEqual(memory_type_display("preference"), "偏好（preference）")
        help_text = memory_type_help_text()

        self.assertIn("记忆类型无效。", help_text)
        self.assertIn("可用类型：", help_text)
        self.assertIn("- 个人资料（profile）", help_text)
        self.assertIn("- 偏好（preference）", help_text)
        self.assertIn("- 群规（group_rule）", help_text)

    def test_add_with_chinese_alias_persists_canonical_type_and_jsonl_stays_english(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(db_path=Path(td) / "memory.sqlite3", exports_dir=Path(td) / "exports")
            canonical = normalize_memory_type("偏好")

            item = store.add_memory("owner-1", "private", "session-1", canonical, "不要骂人")
            stored = store.get_memory("owner-1", "private", item["id"])
            result = store.export_memories("owner-1", "private", "jsonl")
            exported = Path(result["path"])
            row = json.loads(exported.read_text(encoding="utf-8").splitlines()[0])

            self.assertEqual(stored["type"], "preference")
            self.assertEqual(row["type"], "preference")

    def test_main_memory_add_uses_alias_normalization_and_chinese_help(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        main_py = (plugin_root / "main.py").read_text(encoding="utf-8")

        self.assertIn("_normalize_memory_type(raw_memory_type)", main_py)
        self.assertIn('format_memory_command_status("invalid_memory_type")', main_py)
        self.assertIn("memory_type_help_text()", main_py)
        self.assertIn("memory_type_inline_help()", main_py)
        self.assertIn("memory_type_display(str(item.get('type') or ''))", main_py)


if __name__ == "__main__":
    unittest.main()
