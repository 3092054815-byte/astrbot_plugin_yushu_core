from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.memory_console import (
    build_memory_console_snapshot,
    delete_memory_console_item,
    edit_memory_console_item,
    export_memory_console_scope,
    memory_console_hint,
    pin_memory_console_item,
    prune_memory_console_confirm,
    prune_memory_console_dry_run,
    render_memory_console_html,
    type_display_label,
)
from core.memory_store import MemoryLimits, MemoryStore, SQLITE_SCHEMA


class MemoryConsoleTest(unittest.TestCase):
    def _store(self, tmp_path: Path) -> MemoryStore:
        return MemoryStore(
            db_path=tmp_path / "yushu_memory.sqlite3",
            exports_dir=tmp_path / "exports",
            limits=MemoryLimits(max_pinned_memory_per_user=10),
        )

    def test_memory_type_display_labels_cover_known_types_and_fallback(self) -> None:
        self.assertEqual(type_display_label("profile"), "个人资料（profile）")
        self.assertEqual(type_display_label("preference"), "偏好（preference）")
        self.assertEqual(type_display_label("boundary"), "边界（boundary）")
        self.assertEqual(type_display_label("open_thread"), "未完话题（open_thread）")
        self.assertEqual(type_display_label("skill_goal"), "练习目标（skill_goal）")
        self.assertEqual(type_display_label("relationship"), "关系线索（relationship）")
        self.assertEqual(type_display_label("fact"), "事实（fact）")
        self.assertEqual(type_display_label("group_rule"), "群规（group_rule）")
        self.assertEqual(type_display_label("unknown_type"), "unknown_type")

    def test_no_db_returns_safe_empty_state_without_creating_db(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            store = self._store(tmp_path)

            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1"]},
            )

            self.assertFalse((tmp_path / "yushu_memory.sqlite3").exists())
            self.assertEqual(snapshot["status"]["db_size"], "0B")
            self.assertEqual(snapshot["status"]["memory_count"], 0)
            self.assertEqual(snapshot["items"], [])
            self.assertIsNone(snapshot["detail"])
            self.assertNotIn("owner-1", render_memory_console_html(snapshot))
            self.assertNotIn(str(tmp_path), render_memory_console_html(snapshot))

    def test_default_owner_prefers_existing_private_memories(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            session_like_owner = "default:FriendMessage:owner123456"
            bare_like_owner = "owner123456"
            store.add_memory(
                bare_like_owner,
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": [session_like_owner, bare_like_owner]},
            )

            self.assertEqual(snapshot["selected_owner"], "owner_2")
            self.assertEqual(snapshot["status"]["memory_count"], 1)
            self.assertEqual(len(snapshot["items"]), 1)
            self.assertEqual(snapshot["owner_options"], ["owner_1", "owner_2"])
            self.assertEqual(
                snapshot["owner_details"],
                [
                    {
                        "key": "owner_1",
                        "label": "Owner 1（会话ID，0条私聊记忆）",
                        "kind": "session-like",
                        "memory_count": 0,
                        "has_private_memories": False,
                    },
                    {
                        "key": "owner_2",
                        "label": "Owner 2（用户ID，1条私聊记忆）",
                        "kind": "bare-like",
                        "memory_count": 1,
                        "has_private_memories": True,
                    },
                ],
            )
            self.assertEqual(
                snapshot["selected_owner_hint"],
                "当前选择：Owner 2（用户ID，1条私聊记忆）",
            )
            rendered = render_memory_console_html(snapshot)
            self.assertNotIn(session_like_owner, rendered)
            self.assertNotIn(bare_like_owner, rendered)
            self.assertIn("Owner 2（用户ID，1条私聊记忆）", rendered)

    def test_default_owner_uses_first_owner_when_no_private_memories(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))

            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["default:FriendMessage:owner123456", "owner123456"]},
            )

            self.assertEqual(snapshot["selected_owner"], "owner_1")
            self.assertEqual(snapshot["status"]["memory_count"], 0)
            self.assertEqual(snapshot["owner_details"][0]["kind"], "session-like")
            self.assertEqual(snapshot["owner_details"][1]["kind"], "bare-like")
            self.assertEqual(
                snapshot["selected_owner_hint"],
                "当前选择：Owner 1（会话ID，0条私聊记忆）",
            )

    def test_default_owner_picks_largest_private_memory_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "preference", "一条")
            store.add_memory("owner-2", "private", "s2", "preference", "第一条")
            store.add_memory("owner-2", "private", "s3", "fact", "第二条")

            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1", "owner-2"]},
            )

            self.assertEqual(snapshot["selected_owner"], "owner_2")
            self.assertEqual(snapshot["status"]["memory_count"], 2)

    def test_list_shows_only_selected_owner_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            owner_private = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )
            store.add_memory(
                "owner-2",
                "private",
                "other-session",
                "preference",
                "其他 owner 的内容",
            )
            store.add_memory(
                "owner-1",
                "group:123456",
                "group-session",
                "group_rule",
                "群规则内容",
            )

            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1", "owner-2"]},
            )

            self.assertEqual([item["id"] for item in snapshot["items"]], [owner_private["id"]])
            self.assertEqual(snapshot["items"][0]["type_label"], "偏好（preference）")
            html = render_memory_console_html(snapshot)
            self.assertIn("喜欢短句", html)
            self.assertIn("偏好（preference）", html)
            self.assertNotIn("其他 owner 的内容", html)
            self.assertNotIn("群规则内容", html)
            self.assertNotIn("owner-1", html)
            self.assertNotIn("private-session", html)
            self.assertNotIn("group-session", html)

    def test_filters_type_pinned_and_masked_group_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            first = store.add_memory(
                "owner-1",
                "private",
                "s1",
                "preference",
                "喜欢短句",
            )
            second = store.add_memory(
                "owner-1",
                "private",
                "s2",
                "fact",
                "会写 Python",
            )
            group_item = store.add_memory(
                "owner-1",
                "group:123456",
                "group-session",
                "group_rule",
                "群里不要刷屏",
            )
            store.set_pinned("owner-1", "private", second["id"], True)

            private_snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1"]},
                memory_type="fact",
                pinned="true",
            )
            self.assertEqual([item["id"] for item in private_snapshot["items"]], [second["id"]])

            group_snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1"]},
                scope_key="group_rule_1",
            )
            self.assertEqual([item["id"] for item in group_snapshot["items"]], [group_item["id"]])
            html = render_memory_console_html(group_snapshot)
            self.assertIn("group_rule_1", html)
            self.assertNotIn("group:123456", html)
            self.assertNotIn(first["id"], html)

    def test_sensitive_content_is_hidden_in_list_and_detail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            conn = sqlite3.connect(store.db_path)
            conn.executescript(SQLITE_SCHEMA)
            conn.execute(
                """
                INSERT INTO memory_items (
                  id, scope, session_id, user_id, type, content, confidence,
                  created_at, updated_at, expires_at, source, pinned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "sensitive-1",
                    "private",
                    "private-session",
                    "owner-1",
                    "fact",
                    "password=secret",
                    1.0,
                    "2026-05-15T00:00:00+08:00",
                    "2026-05-15T00:00:00+08:00",
                    None,
                    "manual",
                    0,
                ),
            )
            conn.commit()
            conn.close()

            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1"]},
                memory_id="sensitive-1",
            )

            self.assertEqual(snapshot["items"][0]["short_content"], "<hidden>")
            self.assertEqual(snapshot["detail"]["content"], "<hidden>")
            html = render_memory_console_html(snapshot)
            self.assertIn("&lt;hidden&gt;", html)
            self.assertNotIn("password=secret", html)
            self.assertNotIn("private-session", html)

    def test_delete_current_owner_current_scope_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            result = delete_memory_console_item(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                confirm=True,
            )

            self.assertTrue(result["deleted"])
            self.assertEqual(result["memory_id"], item["id"])
            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
            )
            self.assertEqual(snapshot["status"]["memory_count"], 0)
            self.assertEqual(snapshot["items"], [])

    def test_delete_other_owner_returns_memory_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-2",
                "private",
                "other-session",
                "preference",
                "其他 owner 内容",
            )

            with self.assertRaisesRegex(Exception, "memory_not_found"):
                delete_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1", "owner-2"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=item["id"],
                    confirm=True,
                )

            self.assertEqual(store.count_memories("owner-2", "private"), 1)

    def test_delete_other_scope_returns_memory_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "group:123456",
                "group-session",
                "group_rule",
                "群规则内容",
            )

            with self.assertRaisesRegex(Exception, "memory_not_found"):
                delete_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=item["id"],
                    confirm=True,
                )

            self.assertEqual(store.count_memories("owner-1", "group:123456"), 1)

    def test_delete_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            with self.assertRaisesRegex(Exception, "delete_confirm_required"):
                delete_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=item["id"],
                    confirm=False,
                )

            self.assertEqual(store.count_memories("owner-1", "private"), 1)

    def test_delete_payload_does_not_leak_owner_session_or_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "default:FriendMessage:owner123456",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            result = delete_memory_console_item(
                store,
                {"owner_user_ids": ["default:FriendMessage:owner123456"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                confirm="confirm",
            )
            rendered = str(result)

            self.assertNotIn("default:FriendMessage:owner123456", rendered)
            self.assertNotIn("private-session", rendered)
            self.assertNotIn("喜欢短句", rendered)

    def test_edit_current_owner_current_scope_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            result = edit_memory_console_item(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                memory_type="fact",
                content="改成事实",
                confirm=True,
            )

            self.assertTrue(result["updated"])
            updated = store.get_memory("owner-1", "private", item["id"])
            self.assertEqual(updated["type"], "fact")
            self.assertEqual(updated["content"], "改成事实")

    def test_edit_other_owner_returns_memory_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-2",
                "private",
                "other-session",
                "preference",
                "其他 owner 内容",
            )

            with self.assertRaisesRegex(Exception, "memory_not_found"):
                edit_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1", "owner-2"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=item["id"],
                    memory_type="fact",
                    content="不应写入",
                    confirm=True,
                )

            self.assertEqual(store.get_memory("owner-2", "private", item["id"])["type"], "preference")

    def test_edit_other_scope_returns_memory_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "group:123456",
                "group-session",
                "group_rule",
                "群规则内容",
            )

            with self.assertRaisesRegex(Exception, "memory_not_found"):
                edit_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=item["id"],
                    memory_type="fact",
                    content="不应写入",
                    confirm=True,
                )

            self.assertEqual(store.get_memory("owner-1", "group:123456", item["id"])["content"], "群规则内容")

    def test_sensitive_edit_is_rejected_and_db_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            with self.assertRaisesRegex(Exception, "sensitive_content"):
                edit_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=item["id"],
                    memory_type="fact",
                    content="token=abc",
                    confirm=True,
                )

            unchanged = store.get_memory("owner-1", "private", item["id"])
            self.assertEqual(unchanged["type"], "preference")
            self.assertEqual(unchanged["content"], "喜欢短句")

    def test_pin_and_unpin_update_pinned_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            pinned = pin_memory_console_item(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                pinned=True,
            )
            self.assertTrue(pinned["pinned"])
            self.assertEqual(store.status("owner-1", "private")["pinned_count"], 1)

            unpinned = pin_memory_console_item(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                pinned=False,
            )
            self.assertFalse(unpinned["pinned"])
            self.assertEqual(store.status("owner-1", "private")["pinned_count"], 0)

    def test_pin_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(
                db_path=Path(td) / "yushu_memory.sqlite3",
                exports_dir=Path(td) / "exports",
                limits=MemoryLimits(max_pinned_memory_per_user=1),
            )
            first = store.add_memory("owner-1", "private", "s1", "fact", "第一条")
            second = store.add_memory("owner-1", "private", "s2", "fact", "第二条")
            store.set_pinned("owner-1", "private", first["id"], True)

            with self.assertRaisesRegex(Exception, "pinned_limit_exceeded"):
                pin_memory_console_item(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    memory_id=second["id"],
                    pinned=True,
                )

            self.assertEqual(store.status("owner-1", "private")["pinned_count"], 1)

    def test_edit_pin_payloads_do_not_leak_owner_session_or_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            item = store.add_memory(
                "default:FriendMessage:owner123456",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )

            edit_result = edit_memory_console_item(
                store,
                {"owner_user_ids": ["default:FriendMessage:owner123456"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                memory_type="fact",
                content="改成事实",
                confirm=True,
            )
            pin_result = pin_memory_console_item(
                store,
                {"owner_user_ids": ["default:FriendMessage:owner123456"]},
                owner_key="owner_1",
                scope_key="private",
                memory_id=item["id"],
                pinned=True,
            )
            rendered = f"{edit_result} {pin_result}"

            self.assertNotIn("default:FriendMessage:owner123456", rendered)
            self.assertNotIn("private-session", rendered)
            self.assertNotIn("喜欢短句", rendered)
            self.assertNotIn("改成事实", rendered)

    def test_export_md_only_current_owner_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "preference", "喜欢短句")
            store.add_memory("owner-2", "private", "s2", "fact", "其他 owner 内容")
            store.add_memory("owner-1", "group:123", "s3", "group_rule", "群规则内容")

            result = export_memory_console_scope(
                store,
                {"owner_user_ids": ["owner-1", "owner-2"]},
                owner_key="owner_1",
                scope_key="private",
                export_format="md",
            )

            self.assertEqual(result["format"], "md")
            self.assertEqual(result["exported_count"], 1)
            self.assertEqual(result["skipped_sensitive_count"], 0)
            self.assertTrue(str(result["relative_path"]).startswith("exports/"))
            self.assertNotIn(str(Path(td)), str(result))
            self.assertNotIn("owner-1", str(result))
            self.assertNotIn("s1", str(result))
            exported = next((Path(td) / "exports").glob("*.md"))
            body = exported.read_text(encoding="utf-8")
            self.assertIn("喜欢短句", body)
            self.assertNotIn("其他 owner 内容", body)
            self.assertNotIn("群规则内容", body)

    def test_export_jsonl_only_current_owner_scope_and_masks_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory(
                "default:FriendMessage:owner123456",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )
            store.add_memory("other-owner", "private", "other-session", "fact", "其他内容")

            result = export_memory_console_scope(
                store,
                {"owner_user_ids": ["default:FriendMessage:owner123456", "other-owner"]},
                owner_key="owner_1",
                scope_key="private",
                export_format="jsonl",
            )

            self.assertEqual(result["format"], "jsonl")
            self.assertEqual(result["exported_count"], 1)
            rendered = str(result)
            self.assertNotIn("default:FriendMessage:owner123456", rendered)
            self.assertNotIn("private-session", rendered)
            self.assertNotIn(str(Path(td)), rendered)
            exported = next((Path(td) / "exports").glob("*.jsonl"))
            body = exported.read_text(encoding="utf-8")
            self.assertIn("喜欢短句", body)
            self.assertNotIn("其他内容", body)

    def test_prune_dry_run_does_not_delete_db_or_exports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "open_thread", "临时话题")
            exports_dir = Path(td) / "exports"
            exports_dir.mkdir()
            export_file = exports_dir / "old.md"
            export_file.write_text("old", encoding="utf-8")

            result = prune_memory_console_dry_run(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
            )

            self.assertEqual(result["planned_memories"], 1)
            self.assertEqual(result["deleted_memories"], 0)
            self.assertEqual(result["deleted_export_files"], 0)
            self.assertTrue(result["plan_token"])
            self.assertEqual(store.count_memories("owner-1", "private"), 1)
            self.assertTrue(export_file.exists())

    def test_prune_confirm_requires_dry_run_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "open_thread", "临时话题")

            with self.assertRaisesRegex(Exception, "prune_dry_run_required"):
                prune_memory_console_confirm(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    plan_token="",
                )

    def test_prune_confirm_rejects_mismatched_token(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "open_thread", "临时话题")

            with self.assertRaisesRegex(Exception, "prune_plan_mismatch"):
                prune_memory_console_confirm(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    plan_token="bad-token",
                )

            self.assertEqual(store.count_memories("owner-1", "private"), 1)

    def test_prune_confirm_rejects_changed_plan_after_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "open_thread", "临时话题")
            dry_run = prune_memory_console_dry_run(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
            )
            store.add_memory("owner-1", "private", "s2", "open_thread", "新增临时话题")

            with self.assertRaisesRegex(Exception, "prune_plan_mismatch"):
                prune_memory_console_confirm(
                    store,
                    {"owner_user_ids": ["owner-1"]},
                    owner_key="owner_1",
                    scope_key="private",
                    plan_token=dry_run["plan_token"],
                )

            self.assertEqual(store.count_memories("owner-1", "private"), 2)

    def test_prune_confirm_success_updates_capacity_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "open_thread", "临时话题")
            dry_run = prune_memory_console_dry_run(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
            )

            result = prune_memory_console_confirm(
                store,
                {"owner_user_ids": ["owner-1"]},
                owner_key="owner_1",
                scope_key="private",
                plan_token=dry_run["plan_token"],
            )

            self.assertEqual(result["deleted_memories"], 1)
            self.assertEqual(result["status"]["memory_count"], 0)
            self.assertEqual(store.count_memories("owner-1", "private"), 0)

    def test_rendered_page_has_only_single_item_write_actions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            snapshot = build_memory_console_snapshot(
                store,
                {"owner_user_ids": ["owner-1"]},
            )

            html = render_memory_console_html(snapshot)

            self.assertIn("单条操作", html)
            self.assertNotIn('method="post"', html.lower())
            self.assertIn("删除", html)
            self.assertIn("编辑", html)
            self.assertIn("置顶", html)
            self.assertNotIn("memory_add", html)
            self.assertNotIn("clear private", html.lower())

    def test_plugin_page_static_entry_exists_and_uses_bridge_readonly(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        page_path = plugin_root / "pages" / "memory-console" / "index.html"

        html = page_path.read_text(encoding="utf-8")

        self.assertIn("<title>记忆管理</title>", html)
        self.assertIn("<h1>记忆管理</h1>", html)
        self.assertIn("单条操作和当前 Owner/范围导出清理", html)
        self.assertIn("类型说明", html)
        for label in [
            "个人资料",
            "偏好",
            "边界",
            "未完话题",
            "练习目标",
            "关系线索",
            "事实",
            "群规",
        ]:
            self.assertIn(label, html)
        self.assertIn("稳定身份/背景摘要。", html)
        self.assertIn("群聊层面的公开规则，不用于 owner 私聊亲密记忆。", html)
        self.assertIn("AstrBotPluginPage", html)
        self.assertIn("apiGet", html)
        self.assertIn("apiPost", html)
        self.assertIn('const ENDPOINT = "memory-console";', html)
        self.assertIn('const DELETE_ENDPOINT = "memory-console/delete";', html)
        self.assertIn('const EDIT_ENDPOINT = "memory-console/edit";', html)
        self.assertIn('const PIN_ENDPOINT = "memory-console/pin";', html)
        self.assertIn('const UNPIN_ENDPOINT = "memory-console/unpin";', html)
        self.assertIn("Stage 6A-4 export prune build", html)
        self.assertIn("数据库大小", html)
        self.assertIn("导出文件大小", html)
        self.assertIn("记忆条数", html)
        self.assertIn("置顶条数", html)
        self.assertIn("当前 Owner", html)
        self.assertIn("范围", html)
        self.assertIn("类型", html)
        self.assertIn("置顶状态", html)
        self.assertIn("应用", html)
        self.assertIn("详情", html)
        self.assertIn("暂无记忆", html)
        self.assertIn("已置顶", html)
        self.assertIn("未置顶", html)
        self.assertIn("ownerHint", html)
        self.assertIn("data-action", html)
        self.assertIn("delete-memory", html)
        self.assertIn("edit-memory", html)
        self.assertIn("pin-memory", html)
        self.assertIn("unpin-memory", html)
        self.assertIn("data-memory-id", html)
        self.assertIn("data-memory-type", html)
        self.assertIn("data-memory-content", html)
        self.assertIn("editPanel", html)
        self.assertIn("editType", html)
        self.assertIn("editContent", html)
        self.assertIn("编辑确认", html)
        self.assertIn('const ACTION_ENDPOINT = "memory-console/action";', html)
        self.assertIn('action: "export"', html)
        self.assertIn('action: "prune_dry_run"', html)
        self.assertIn('action: "prune_confirm"', html)
        self.assertNotIn('apiPost("memory-console/export"', html)
        self.assertNotIn('apiPost("memory-console/prune-dry-run"', html)
        self.assertNotIn('apiPost("memory-console/prune-confirm"', html)
        self.assertIn("export-md", html)
        self.assertIn("export-jsonl", html)
        self.assertIn("prune-dry-run", html)
        self.assertIn("prune-confirm", html)
        self.assertIn("pruneConfirmPanel", html)
        self.assertIn("exported_count", html)
        self.assertIn("planned_memories", html)
        self.assertIn("/root/astrbot/data/plugin_data/astrbot_plugin_yushu_core/exports/", html)
        self.assertIn("/AstrBot/data/plugin_data/astrbot_plugin_yushu_core/exports/", html)
        self.assertIn("let lastPrunePlan = null;", html)
        self.assertIn("lastPrunePlan = {", html)
        self.assertIn("token: data.plan_token", html)
        self.assertIn("ownerKey: currentOwnerKey()", html)
        self.assertIn("scope: currentScopeKey()", html)
        self.assertIn("plan_token: lastPrunePlan.token", html)
        self.assertIn("clearPrunePlan();", html)
        self.assertIn("请先重新清理预览", html)
        self.assertIn("没有需要清理的项目", html)
        self.assertIn("plan: ready", html)
        self.assertIn('document.addEventListener("click"', html)
        self.assertIn("Plugin Page bridge 未加载", html)
        self.assertIn("删除失败：", html)
        self.assertIn("保存失败：", html)
        self.assertIn("导出失败：", html)
        self.assertIn("清理失败：", html)
        self.assertIn("typeof window.AstrBotPluginPage.apiPost", html)
        self.assertNotIn('apiGet("/api/plug/', html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("window.confirm", html)
        self.assertNotIn("window.prompt", html)
        self.assertIn("单条操作", html)
        self.assertNotIn('method="post"', html.lower())

    def test_memory_console_hint_points_to_authenticated_webui_page(self) -> None:
        hint = memory_console_hint()

        self.assertEqual(
            hint,
            "Memory Console: 在 AstrBot WebUI -> 插件管理 -> yushu_core -> memory-console 页面打开",
        )
        self.assertNotIn("/api/plug", hint)
        self.assertNotIn("http://", hint)
        self.assertNotIn("https://", hint)


if __name__ == "__main__":
    unittest.main()
