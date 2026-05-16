from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.command_format import (
    config_audit_report,
    config_diff_report,
    format_yushu_help,
    get_help_commands,
    format_memory_command_status,
    format_memory_list,
    format_memory_view,
)
from core.mvp_doctor import build_doctor_report
from core.memory_store import MemoryStore


class CommandFormatTest(unittest.TestCase):
    def test_memory_list_output_is_chinese_with_type_label(self) -> None:
        text = format_memory_list(
            [
                {
                    "id": "433cbc2e5e48",
                    "type": "preference",
                    "pinned": 0,
                    "created_at": "2026-05-15T00:49:29+08:00",
                    "short_content": "喜欢简短直接的回复",
                }
            ]
        )

        self.assertIn("雨舒记忆列表", text)
        self.assertIn("ID：433cbc2e5e48", text)
        self.assertIn("类型：偏好（preference）", text)
        self.assertIn("置顶：否", text)
        self.assertIn("创建时间：2026-05-15T00:49:29+08:00", text)
        self.assertIn("内容摘要：喜欢简短直接的回复", text)
        self.assertNotIn("session", text.lower())
        self.assertNotIn("db_path", text.lower())

    def test_memory_view_output_is_chinese_with_scope_and_pinned_labels(self) -> None:
        text = format_memory_view(
            {
                "id": "433cbc2e5e48",
                "scope": "private",
                "type": "preference",
                "content": "喜欢简短直接的回复",
                "confidence": 1.0,
                "created_at": "2026-05-15T00:49:29+08:00",
                "updated_at": "2026-05-15T00:49:29+08:00",
                "expires_at": None,
                "source": "manual",
                "pinned": 0,
            }
        )

        self.assertIn("雨舒记忆详情", text)
        self.assertIn("范围：私聊", text)
        self.assertIn("类型：偏好（preference）", text)
        self.assertIn("置顶：否", text)
        self.assertIn("来源：手动", text)
        self.assertIn("过期时间：无", text)

    def test_memory_status_messages_are_chinese(self) -> None:
        self.assertEqual(format_memory_command_status("memory_empty"), "记忆为空")
        self.assertEqual(format_memory_command_status("memory_not_found"), "未找到这条记忆")
        self.assertEqual(format_memory_command_status("memory_added", "abc123"), "已新增记忆：abc123")
        self.assertEqual(format_memory_command_status("memory_deleted"), "已删除记忆")
        self.assertEqual(format_memory_command_status("memory_edited", "abc123"), "已更新记忆：abc123")
        self.assertEqual(format_memory_command_status("memory_pinned", "abc123"), "已置顶：abc123")
        self.assertEqual(format_memory_command_status("memory_unpinned", "abc123"), "已取消置顶：abc123")
        self.assertEqual(format_memory_command_status("memory_off"), "记忆功能已关闭")
        self.assertEqual(format_memory_command_status("memory_on"), "记忆功能已开启")
        self.assertEqual(format_memory_command_status("memory_exported"), "记忆已导出")

    def test_jsonl_export_keeps_english_type(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(db_path=Path(td) / "memory.sqlite3", exports_dir=Path(td) / "exports")
            store.add_memory("owner-1", "private", "session-1", "preference", "喜欢简短直接的回复")

            result = store.export_memories("owner-1", "private", "jsonl")
            exported = Path(result["path"])
            row = json.loads(exported.read_text(encoding="utf-8").splitlines()[0])

            self.assertEqual(row["type"], "preference")

    def test_config_audit_reports_risks_without_leaks(self) -> None:
        report = config_audit_report(
            {
                "owner_user_ids": ["default:FriendMessage:owner123456"],
                "debug_mode": True,
                "prompt_injection_enabled": False,
                "memory_injection_enabled": False,
                "proactive_enabled": True,
                "yushu_group_enabled": True,
                "coach_review_enabled": True,
                "state_machine_enabled": False,
                "memory_mode": "suggest",
            }
        )

        self.assertIn("雨舒配置检查", report)
        self.assertIn("调试模式：已开启", report)
        self.assertIn("建议正式使用前关闭调试模式。", report)
        self.assertIn("真实聊天不会注入雨舒上下文。", report)
        self.assertIn("主动消息仍需确认 reason gate。", report)
        self.assertIn("群聊能力已开启，请确认隔离。", report)
        self.assertNotIn("owner123456", report)
        self.assertNotIn("FriendMessage", report)
        self.assertNotIn("/root", report)

    def test_config_audit_reports_no_high_priority_risk(self) -> None:
        report = config_audit_report(
            {
                "debug_mode": False,
                "prompt_injection_enabled": True,
                "memory_injection_enabled": True,
                "proactive_enabled": False,
                "yushu_group_enabled": False,
                "coach_review_enabled": True,
                "state_machine_enabled": False,
                "memory_mode": "suggest",
            }
        )

        self.assertIn("当前没有高优先级配置风险", report)

    def test_config_audit_command_is_registered_readonly(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        main_py = (plugin_root / "main.py").read_text(encoding="utf-8")

        self.assertIn('@ys.group("config")', main_py)
        self.assertIn('@config_commands.command("audit")', main_py)
        self.assertIn("config_audit_report(self.config)", main_py)

    def test_config_diff_reports_changed_and_matching_items_without_mutation(self) -> None:
        config = {
            "owner_user_ids": ["default:FriendMessage:owner123456"],
            "prompt_injection_enabled": False,
            "memory_injection_enabled": False,
            "debug_mode": True,
            "proactive_enabled": True,
            "yushu_group_enabled": True,
            "coach_review_enabled": True,
            "state_machine_enabled": False,
            "memory_mode": "suggest",
        }
        original = dict(config)

        report = config_diff_report(config)

        self.assertEqual(config, original)
        self.assertIn("雨舒配置建议 diff", report)
        self.assertIn("需要调整：", report)
        self.assertIn("提示词注入：当前 已关闭 -> 建议 已开启", report)
        self.assertIn("原因：不开启时真实聊天不会注入雨舒上下文。", report)
        self.assertIn("记忆注入：当前 已关闭 -> 建议 已开启", report)
        self.assertIn("调试模式：当前 已开启 -> 建议 已关闭", report)
        self.assertIn("主动消息：当前 已开启 -> 建议 已关闭", report)
        self.assertIn("群聊雨舒能力：当前 已开启 -> 建议 已关闭", report)
        self.assertIn("无需调整：", report)
        self.assertIn("复盘模式：已开启", report)
        self.assertIn("状态机：已关闭", report)
        self.assertIn("这里只读展示建议，不会自动修改配置。", report)
        self.assertNotIn("owner123456", report)
        self.assertNotIn("FriendMessage", report)
        self.assertNotIn("/root", report)

    def test_config_diff_reports_missing_values_as_unconfigured(self) -> None:
        report = config_diff_report({})

        self.assertIn("提示词注入：当前 未配置 -> 建议 已开启", report)
        self.assertIn("私聊雨舒：当前 未配置 -> 建议 已开启", report)

    def test_config_diff_command_is_registered_readonly(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        main_py = (plugin_root / "main.py").read_text(encoding="utf-8")

        self.assertIn('@config_commands.command("diff")', main_py)
        self.assertIn("config_diff_report(self.config)", main_py)

    def test_doctor_report_is_readonly_masked_and_checks_mvp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            store = MemoryStore(
                db_path=tmp_path / "yushu_memory.sqlite3",
                exports_dir=tmp_path / "exports",
            )
            item = store.add_memory(
                "owner-1",
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )
            store.set_pinned("owner-1", "private", item["id"], True)

            report = build_doctor_report(
                config={
                    "owner_user_ids": ["owner-1"],
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "debug_mode": False,
                    "state_machine_enabled": False,
                    "proactive_enabled": False,
                    "yushu_group_enabled": False,
                },
                store=store,
                owner_id="owner-1",
                eval_summary={
                    "exists": True,
                    "case_count": 55,
                    "declared_case_count": 55,
                },
                plugin_root=Path(__file__).resolve().parents[1],
            )

            self.assertIn("雨舒 Doctor", report)
            self.assertIn("插件阶段：mvp_ready_check", report)
            self.assertIn("推荐配置：", report)
            self.assertIn("记忆 DB：存在", report)
            self.assertIn("记忆条数：1", report)
            self.assertIn("置顶条数：1", report)
            self.assertIn("Console 页面：存在", report)
            self.assertIn("Memory Console 页面：存在", report)
            self.assertIn("评估用例数量：55（符合）", report)
            self.assertIn("提示词注入：已开启", report)
            self.assertIn("群聊隔离：通过，群聊不注入 owner 私聊记忆", report)
            self.assertIn("需要人工验证：", report)
            self.assertIn("WebUI 插件页能打开雨舒总览和记忆管理。", report)
            self.assertNotIn("owner-1", report)
            self.assertNotIn("private-session", report)
            self.assertNotIn(str(tmp_path), report)
            self.assertNotIn("喜欢短句", report)

    def test_help_output_is_short_chinese_command_reference(self) -> None:
        text = format_yushu_help()
        commands = get_help_commands()

        self.assertIn("雨舒命令帮助", text)
        self.assertEqual(len(commands), 10)
        self.assertIn("/ys status：查看雨舒 Core 基础状态。", text)
        self.assertIn("/ys doctor：运行 MVP 只读诊断。", text)
        self.assertIn("/ys config audit：查看当前配置风险提示。", text)
        self.assertIn("/ys config diff：查看当前值到推荐值的配置差异。", text)
        self.assertIn("/ys injection status：查看提示词注入、记忆注入和复盘模式开关。", text)
        self.assertIn("/ys memory add 偏好 <内容>：手动新增一条偏好记忆。", text)
        self.assertIn(
            "记忆类型可用中文或英文：个人资料、偏好、边界、未完话题、练习目标、关系线索、事实、群规。",
            text,
        )
        self.assertIn("/ys memory prune dry-run：预览可清理项目，不会真的删除。", text)
        self.assertNotIn("owner_user_ids", text)
        self.assertNotIn("db_path", text)
        self.assertNotIn("profile/个人资料，preference/偏好", text)

    def test_doctor_and_help_commands_are_registered_readonly(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        main_py = (plugin_root / "main.py").read_text(encoding="utf-8")

        self.assertIn('@ys.command("doctor")', main_py)
        self.assertIn('@ys.command("help")', main_py)
        self.assertIn("build_doctor_report(", main_py)
        self.assertIn("format_yushu_help()", main_py)


if __name__ == "__main__":
    unittest.main()
