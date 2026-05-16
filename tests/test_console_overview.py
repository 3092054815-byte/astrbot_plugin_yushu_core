from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.console_overview import build_console_overview_status
from core.command_format import get_help_commands
from core.memory_store import MemoryLimits, MemoryStore


class ConsoleOverviewTest(unittest.TestCase):
    def _store(self, tmp_path: Path) -> MemoryStore:
        return MemoryStore(
            db_path=tmp_path / "yushu_memory.sqlite3",
            exports_dir=tmp_path / "exports",
            limits=MemoryLimits(max_pinned_memory_per_user=10),
        )

    def test_status_returns_switches_keywords_and_capacity_without_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            store = self._store(tmp_path)
            owner = "default:FriendMessage:owner123456"
            item = store.add_memory(
                owner,
                "private",
                "private-session",
                "preference",
                "喜欢短句",
            )
            store.set_pinned(owner, "private", item["id"], True)

            status = build_console_overview_status(
                store,
                {
                    "owner_user_ids": [owner],
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "state_machine_enabled": False,
                    "debug_mode": False,
                    "coach_review_trigger_keywords": ["复盘", "评分"],
                    "coach_review_exit_keywords": ["正常聊"],
                },
            )
            rendered = str(status)

            self.assertEqual(status["stage"], "stage6b_console_overview")
            self.assertEqual(status["plugin_version"], "0.1.0")
            self.assertTrue(status["switches"]["prompt_injection_enabled"])
            self.assertTrue(status["switches"]["memory_injection_enabled"])
            self.assertTrue(status["switches"]["coach_review_enabled"])
            self.assertFalse(status["switches"]["state_machine_enabled"])
            self.assertEqual(status["owner"]["owner_count"], 1)
            self.assertEqual(status["owner"]["selected_owner"], "owner_1")
            self.assertIn("Owner 1", status["owner"]["selected_owner_hint"])
            self.assertEqual(status["memory"]["memory_count"], 1)
            self.assertEqual(status["memory"]["pinned_count"], 1)
            self.assertEqual(status["memory"]["runtime_enabled"], True)
            self.assertEqual(status["memory"]["paused_until"], "none")
            self.assertEqual(status["coach_review_trigger_keywords"], ["复盘", "评分"])
            self.assertEqual(status["coach_review_exit_keywords"], ["正常聊"])
            self.assertEqual(status["commands"], get_help_commands())
            self.assertEqual(len(status["commands"]), len(get_help_commands()))
            self.assertIn(
                {
                    "command": "/ys doctor",
                    "description": "运行 MVP 只读诊断。",
                },
                status["commands"],
            )
            self.assertEqual(
                status["memory_type_short_help"],
                "记忆类型：个人资料、偏好、边界、未完话题、练习目标、关系线索、事实、群规。",
            )
            self.assertEqual(
                status["links"]["memory_console"],
                "#/plugin-page/yushu_core/memory-console",
            )
            self.assertEqual(
                status["safety"]["group_memory_isolation"],
                "群聊不注入 owner 私聊记忆",
            )
            health_checks = status["health_checks"]
            self.assertIn(
                {
                    "status": "通过",
                    "item": "群聊隔离",
                    "message": "群聊不注入 owner 私聊记忆",
                },
                health_checks,
            )
            self.assertIn(
                {
                    "status": "通过",
                    "item": "记忆管理页",
                    "message": "记忆管理页可用",
                },
                health_checks,
            )
            self.assertNotIn(owner, rendered)
            self.assertNotIn("private-session", rendered)
            self.assertNotIn(str(tmp_path), rendered)
            self.assertNotIn("喜欢短句", rendered)

    def test_status_handles_no_owner_without_creating_db(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            store = self._store(tmp_path)

            status = build_console_overview_status(store, {})

            self.assertFalse((tmp_path / "yushu_memory.sqlite3").exists())
            self.assertEqual(status["owner"]["owner_count"], 0)
            self.assertEqual(status["owner"]["selected_owner"], "owner_none")
            self.assertEqual(status["memory"]["memory_count"], 0)
            self.assertEqual(status["memory"]["pinned_count"], 0)

    def test_health_checks_warn_for_debug_disabled_prompt_and_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            store = MemoryStore(
                db_path=tmp_path / "yushu_memory.sqlite3",
                exports_dir=tmp_path / "exports",
                limits=MemoryLimits(
                    memory_total_limit_mb=1,
                    max_pinned_memory_per_user=10,
                ),
            )
            owner = "owner-1"
            store.add_memory(owner, "private", "private-session", "fact", "a" * 80)
            exports_dir = tmp_path / "exports"
            exports_dir.mkdir(exist_ok=True)
            (exports_dir / "large.md").write_bytes(b"x" * 900_000)

            status = build_console_overview_status(
                store,
                {
                    "owner_user_ids": [owner],
                    "debug_mode": True,
                    "prompt_injection_enabled": False,
                    "coach_review_enabled": False,
                    "proactive_enabled": True,
                    "state_machine_enabled": True,
                },
            )
            rendered = str(status)
            messages = [item["message"] for item in status["health_checks"]]

            self.assertIn("建议关闭调试模式，避免日志过多", messages)
            self.assertIn("live 注入未开启，雨舒人格/记忆不会进入真实聊天", messages)
            self.assertIn("复盘模式关闭，触发词不会进入复盘", messages)
            self.assertIn("主动消息已开启，请确认 reason gate 仍未接管或频率安全", messages)
            self.assertIn("状态机已开启，请确认仍只控制表达分寸", messages)
            self.assertIn("记忆数据接近容量上限，建议导出或清理", messages)
            self.assertNotIn(owner, rendered)
            self.assertNotIn("private-session", rendered)
            self.assertNotIn(str(tmp_path), rendered)

    def test_plugin_page_static_entry_exists_and_is_readonly(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        page_path = plugin_root / "pages" / "console" / "index.html"

        html = page_path.read_text(encoding="utf-8")

        self.assertIn("<title>雨舒总览</title>", html)
        self.assertIn("<h1>雨舒总览</h1>", html)
        self.assertIn("Stage 6B console overview build", html)
        self.assertIn("只读总览", html)
        self.assertIn("<h2>健康检查</h2>", html)
        self.assertIn("当前没有高优先级风险", html)
        self.assertIn("通过", html)
        self.assertIn("注意", html)
        self.assertIn("建议", html)
        self.assertIn("AstrBotPluginPage", html)
        self.assertIn("apiGet", html)
        self.assertIn('const STATUS_ENDPOINT = "console/status";', html)
        self.assertIn("<h2>命令速查</h2>", html)
        self.assertNotIn(".panel.wide", html)
        self.assertNotIn("grid-column: 1 / -1", html)
        self.assertNotIn("grid-column: span 2", html)
        self.assertNotIn("grid-column: span 3", html)
        self.assertIn('id="commands-scroll"', html)
        self.assertIn("max-height: 360px", html)
        self.assertIn("overflow-y: auto", html)
        self.assertIn("data.commands", html)
        self.assertIn("memory_type_short_help", html)
        self.assertIn("记忆类型：个人资料、偏好、边界、未完话题、练习目标、关系线索、事实、群规。", html)
        self.assertIn("<span>Owner 群聊</span>", html)
        self.assertIn("<span>主动消息</span>", html)
        self.assertNotIn("<span>proactive</span>", html)
        self.assertNotIn("<span>owner 群聊</span>", html)
        self.assertNotIn("const COMMAND_HELP", html)
        self.assertNotIn("profile/个人资料，preference/偏好", html)
        self.assertNotIn("open_thread/未完话题，skill_goal/练习目标", html)
        self.assertIn("私聊雨舒", html)
        self.assertIn("提示词注入", html)
        self.assertIn("记忆条数", html)
        self.assertIn("复盘触发词", html)
        self.assertIn("已开启", html)
        self.assertIn("已关闭", html)
        self.assertIn("无", html)
        self.assertIn("建议保存", html)
        self.assertIn("请从 AstrBot WebUI 插件页打开", html)
        self.assertIn("群聊不注入 owner 私聊记忆", html)
        self.assertNotIn("打开记忆管理", html)
        self.assertNotIn("复制路径", html)
        self.assertNotIn("#/plugin-page/yushu_core/memory-console", html)
        self.assertNotIn("Memory Console", html)
        self.assertNotIn("MEMORY_CONSOLE_HASH", html)
        self.assertNotIn("window.parent.location.hash", html)
        self.assertNotIn('<a class="link-button"', html)
        self.assertNotIn("target=\"_top\"", html)
        self.assertNotIn("window.open", html)
        self.assertNotIn("apiPost", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("window.confirm", html)
        self.assertNotIn("window.prompt", html)

    def test_command_status_display_uses_chinese_labels(self) -> None:
        plugin_root = Path(__file__).resolve().parents[1]
        main_py = (plugin_root / "main.py").read_text(encoding="utf-8")

        self.assertIn('"雨舒状态"', main_py)
        self.assertIn('f"私聊雨舒：', main_py)
        self.assertIn('f"群聊轻量模式：', main_py)
        self.assertIn('f"提示词注入：', main_py)
        self.assertIn('"雨舒注入状态"', main_py)
        self.assertIn('f"复盘触发词数量：', main_py)
        self.assertIn('f"记忆运行状态：', main_py)


if __name__ == "__main__":
    unittest.main()
