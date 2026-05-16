from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory_injection import build_memory_injection, select_memory_items
from core.memory_store import MemoryLimits, MemoryStore
from core.prompt_fragments import build_owner_private_fragment
from core.yushu_state import is_coach_review_requested, normalize_state


class Stage5InjectionTest(unittest.TestCase):
    def _store(self, tmp_path: Path) -> MemoryStore:
        return MemoryStore(
            db_path=tmp_path / "yushu_memory.sqlite3",
            exports_dir=tmp_path / "exports",
            limits=MemoryLimits(max_pinned_memory_per_user=10),
        )

    def test_memory_sorting_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            fact = store.add_memory("owner-1", "private", "s1", "fact", "低优先级事实")
            boundary = store.add_memory("owner-1", "private", "s1", "boundary", "要尊重边界")
            pinned = store.add_memory("owner-1", "private", "s1", "preference", "置顶偏好内容")
            store.set_pinned("owner-1", "private", pinned["id"], True)

            items = select_memory_items(
                store.list_memories("owner-1", "private"),
                max_items=3,
                char_budget=100,
            )

            self.assertEqual([item["type"] for item in items], ["preference", "boundary", "fact"])
            tight_items = select_memory_items(
                store.list_memories("owner-1", "private"),
                max_items=3,
                char_budget=len("置顶偏好内容"),
            )
            self.assertEqual([item["content"] for item in tight_items], ["置顶偏好内容"])

    def test_sensitive_content_is_filtered(self) -> None:
        rows = [
            {
                "type": "preference",
                "content": "喜欢短句",
                "pinned": 0,
                "created_at": "2026-05-15T00:00:00+08:00",
            },
            {
                "type": "fact",
                "content": "token=abc123",
                "pinned": 1,
                "created_at": "2026-05-15T00:00:01+08:00",
            },
        ]

        items = select_memory_items(rows, max_items=5, char_budget=900)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"], "喜欢短句")

    def test_memory_off_returns_empty_injection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "preference", "喜欢短句")
            store.set_runtime_flag("owner-1", enabled=False)

            result = build_memory_injection(
                store,
                "owner-1",
                {"memory_injection_enabled": True},
            )

            self.assertFalse(result["enabled"])
            self.assertEqual(result["items"], [])
            self.assertEqual(result["reason"], "memory_off")

    def test_prompt_fragment_excludes_ids_and_paths(self) -> None:
        fragment = build_owner_private_fragment(
            [
                {
                    "id": "abc123",
                    "type": "preference",
                    "content": "喜欢短句",
                    "pinned": 1,
                    "session_id": "session-secret",
                }
            ],
            normalize_state({"relationship_warmth": 8}),
        )

        self.assertIn("作用域：owner 私聊", fragment)
        self.assertIn("模式：角色内", fragment)
        self.assertIn("记忆策略：", fragment)
        self.assertIn("短记忆：", fragment)
        self.assertIn("状态提示：", fragment)
        self.assertIn("喜欢短句", fragment)
        self.assertNotIn("abc123", fragment)
        self.assertNotIn("session-secret", fragment)
        self.assertNotIn("/root/", fragment)
        self.assertNotIn("/AstrBot/", fragment)

    def test_group_fragment_is_chinese_and_public(self) -> None:
        from core.prompt_fragments import build_group_light_fragment

        fragment = build_group_light_fragment()

        self.assertIn("作用域：群聊", fragment)
        self.assertIn("模式：群聊轻量", fragment)
        self.assertIn("不使用 owner 私聊记忆", fragment)
        self.assertIn("不改变 SpectreCore 群聊行为", fragment)
        self.assertNotIn("memory id", fragment)
        self.assertNotIn("/root/", fragment)

    def test_coach_review_trigger_words(self) -> None:
        self.assertTrue(is_coach_review_requested("帮我复盘一下哪里不对"))
        self.assertTrue(is_coach_review_requested("现实里怎么练这段沟通"))
        self.assertFalse(is_coach_review_requested("今天正常聊一会"))


if __name__ == "__main__":
    unittest.main()
