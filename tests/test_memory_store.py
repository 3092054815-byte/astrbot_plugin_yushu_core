from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.memory_store import MemoryLimits, MemoryStore, should_reject_memory


class MemoryStoreTest(unittest.TestCase):
    def test_rejects_sensitive_and_overlong_content(self) -> None:
        limits = MemoryLimits(memory_content_max_chars=6)

        rejected, reason = should_reject_memory("保存 password=abc", limits)
        self.assertTrue(rejected)
        self.assertEqual(reason, "sensitive_content")

        rejected, reason = should_reject_memory("这段内容超过长度限制", limits)
        self.assertTrue(rejected)
        self.assertEqual(reason, "content_too_long")

    def test_store_add_edit_pin_export_and_prune(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            store = MemoryStore(
                db_path=tmp_path / "yushu_memory.sqlite3",
                exports_dir=tmp_path / "exports",
                limits=MemoryLimits(
                    max_memory_per_user=3,
                    max_pinned_memory_per_user=1,
                    memory_export_file_limit_kb=512,
                ),
            )

            item = store.add_memory(
                user_id="owner-1",
                scope="private",
                session_id="session-1",
                memory_type="preference",
                content="喜欢简短直接的回复",
            )
            self.assertEqual(item["type"], "preference")
            self.assertEqual(store.count_memories("owner-1", "private"), 1)

            listed = store.list_memories("owner-1", "private")
            self.assertEqual(listed[0]["short_content"], "喜欢简短直接的回复")

            edited = store.edit_memory(
                user_id="owner-1",
                scope="private",
                memory_id=item["id"],
                content="喜欢直接但保留一点温度的回复",
            )
            self.assertEqual(edited["content"], "喜欢直接但保留一点温度的回复")

            pinned = store.set_pinned("owner-1", "private", item["id"], True)
            self.assertEqual(pinned["pinned"], 1)

            exported = store.export_memories("owner-1", "private", "jsonl")
            self.assertTrue(exported["path"].endswith(".jsonl"))
            line = Path(exported["path"]).read_text(encoding="utf-8").strip()
            payload = json.loads(line)
            self.assertNotIn("user_id", payload)
            self.assertEqual(payload["owner"], "current_owner")

            dry_run = store.prune("owner-1", "private", confirm=False)
            self.assertEqual(dry_run["deleted_memories"], 0)
            self.assertEqual(store.count_memories("owner-1", "private"), 1)


if __name__ == "__main__":
    unittest.main()
