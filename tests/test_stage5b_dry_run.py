from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.live_injection import (
    LiveInjectionDryRunResult,
    LiveInjectionError,
    apply_live_injection_to_system_prompt,
    build_live_injection_dry_run,
    format_applied_log_summary,
    format_dry_run_log_summary,
)
from core.memory_store import MemoryLimits, MemoryStore
from core.scope import is_group_scope, is_private_owner
from core.yushu_state import (
    get_coach_review_exit_keywords,
    get_coach_review_trigger_keywords,
    summarize_keywords,
)


class DummyMessageObj:
    def __init__(self, message_type: str = "FriendMessage", session_id: str = ""):
        self.type = message_type
        self.message_type = message_type
        self.session_id = session_id


class DummyEvent:
    def __init__(
        self,
        sender_id: str = "owner-1",
        message_type: str = "FriendMessage",
        session_id: str = "default:FriendMessage:owner-1",
        message: str = "正常聊",
    ):
        self._sender_id = sender_id
        self.message_obj = DummyMessageObj(message_type, session_id)
        self._message = message

    def get_sender_id(self):
        return self._sender_id

    def get_message_str(self):
        return self._message


class DummyRequest:
    def __init__(self):
        self.system_prompt = "base system"
        self.prompt = "base prompt"


class RequestWithoutSystemPrompt:
    def __init__(self):
        self.prompt = "base prompt"


class ReadOnlySystemPromptRequest:
    def __init__(self):
        self.prompt = "base prompt"

    @property
    def system_prompt(self):
        return "base system"


class OnLlmRequestEventWithoutMessageType:
    def __init__(
        self,
        sender_id: str = "owner-1",
        unified_msg_origin: str = "default:FriendMessage:owner-1",
        message: str = "正常聊",
    ):
        self._sender_id = sender_id
        self.unified_msg_origin = unified_msg_origin
        self._message = message

    def get_sender_id(self):
        return self._sender_id

    def get_message_str(self):
        return self._message


class Stage5BDryRunTest(unittest.TestCase):
    def _store(self, tmp_path: Path) -> MemoryStore:
        return MemoryStore(
            db_path=tmp_path / "yushu_memory.sqlite3",
            exports_dir=tmp_path / "exports",
            limits=MemoryLimits(max_pinned_memory_per_user=10),
        )

    def test_prompt_injection_disabled_skips_without_modifying_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(),
                request,
                store,
                {
                    "prompt_injection_enabled": False,
                    "owner_user_ids": ["owner-1"],
                },
            )

            self.assertFalse(result.should_inject)
            self.assertEqual(result.skip_reason, "prompt_injection_disabled")
            self.assertEqual(request.system_prompt, "base system")
            self.assertEqual(request.prompt, "base prompt")

    def test_non_owner_skips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))

            result = build_live_injection_dry_run(
                DummyEvent(sender_id="user-2"),
                DummyRequest(),
                store,
                {
                    "prompt_injection_enabled": True,
                    "owner_user_ids": ["owner-1"],
                },
            )

            self.assertFalse(result.should_inject)
            self.assertEqual(result.skip_reason, "not_owner")

    def test_group_scope_skips_even_for_owner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))

            result = build_live_injection_dry_run(
                DummyEvent(
                    sender_id="owner-1",
                    message_type="GroupMessage",
                    session_id="default:GroupMessage:10001",
                ),
                DummyRequest(),
                store,
                {
                    "prompt_injection_enabled": True,
                    "owner_user_ids": ["owner-1"],
                },
            )

            self.assertFalse(result.should_inject)
            self.assertEqual(result.skip_reason, "not_private")

    def test_scope_normalizes_friend_message_variants(self) -> None:
        variants = [
            "FriendMessage",
            "FRIEND_MESSAGE",
            "friend_message",
            "messagetype.friend_message",
            "MessageType.FRIEND_MESSAGE",
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(is_private_owner(variant, "owner-1", ["owner-1"]))

    def test_scope_normalizes_group_message_variants(self) -> None:
        variants = [
            "GroupMessage",
            "GROUP_MESSAGE",
            "group_message",
            "messagetype.group_message",
            "MessageType.GROUP_MESSAGE",
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertTrue(is_group_scope(variant))

    def test_dry_run_normalizes_friend_message_enum_strings(self) -> None:
        variants = [
            "FriendMessage",
            "FRIEND_MESSAGE",
            "friend_message",
            "messagetype.friend_message",
            "MessageType.FRIEND_MESSAGE",
        ]
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            for variant in variants:
                with self.subTest(variant=variant):
                    result = build_live_injection_dry_run(
                        DummyEvent(
                            sender_id="owner-1",
                            message_type=variant,
                            session_id="default:FriendMessage:owner-1",
                        ),
                        DummyRequest(),
                        store,
                        {
                            "prompt_injection_enabled": True,
                            "owner_user_ids": ["owner-1"],
                        },
                    )
                    self.assertTrue(result.should_inject)
                    self.assertEqual(result.mode, "normal")

    def test_dry_run_normalizes_group_message_enum_strings(self) -> None:
        variants = [
            "GroupMessage",
            "GROUP_MESSAGE",
            "group_message",
            "messagetype.group_message",
            "MessageType.GROUP_MESSAGE",
        ]
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            for variant in variants:
                with self.subTest(variant=variant):
                    result = build_live_injection_dry_run(
                        DummyEvent(
                            sender_id="owner-1",
                            message_type=variant,
                            session_id="default:GroupMessage:10001",
                        ),
                        DummyRequest(),
                        store,
                        {
                            "prompt_injection_enabled": True,
                            "owner_user_ids": ["owner-1"],
                        },
                    )
                    self.assertFalse(result.should_inject)
                    self.assertEqual(result.skip_reason, "not_private")

    def test_dry_run_builds_fragment_without_modifying_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "preference", "喜欢短句")
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(message="帮我正常聊一下"),
                request,
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "state_machine_enabled": True,
                    "owner_user_ids": ["owner-1"],
                },
            )

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "normal")
            self.assertEqual(result.memory_count, 1)
            self.assertGreater(result.char_count, 0)
            self.assertIn("system_prompt", result.request_fields)
            self.assertIn("喜欢短句", result.fragment)
            self.assertEqual(request.system_prompt, "base system")
            self.assertEqual(request.prompt, "base prompt")

    def test_full_session_owner_id_is_supported(self) -> None:
        class EmptyStore:
            def get_runtime_flag(self, owner_user_id):
                return {"enabled": True}

            def list_memories(self, owner_user_id, scope):
                return []

        with tempfile.TemporaryDirectory() as td:
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(
                    sender_id="owner-1",
                    session_id="default:FriendMessage:owner-1",
                ),
                request,
                EmptyStore(),
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "owner_user_ids": ["default:FriendMessage:owner-1"],
                },
            )

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "normal")
            self.assertEqual(request.system_prompt, "base system")

    def test_on_llm_request_owner_private_uses_sender_and_umo_when_message_type_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            request = DummyRequest()

            result = build_live_injection_dry_run(
                OnLlmRequestEventWithoutMessageType(),
                request,
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "owner_user_ids": ["owner-1", "default:FriendMessage:owner-1"],
                },
            )

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "normal")
            self.assertEqual(result.memory_count, 0)
            self.assertEqual(request.system_prompt, "base system")

    def test_exception_fail_closed(self) -> None:
        class BrokenStore:
            def get_runtime_flag(self, owner_user_id):
                raise RuntimeError("sqlite locked")

        result = build_live_injection_dry_run(
            DummyEvent(),
            DummyRequest(),
            BrokenStore(),
            {
                "prompt_injection_enabled": True,
                "memory_injection_enabled": True,
                "owner_user_ids": ["owner-1"],
            },
        )

        self.assertFalse(result.should_inject)
        self.assertEqual(result.skip_reason, "fail_closed")
        self.assertEqual(result.memory_count, 0)
        self.assertEqual(result.char_count, 0)

    def test_log_summary_uses_only_allowed_fields(self) -> None:
        result = LiveInjectionDryRunResult(
            should_inject=True,
            skip_reason="",
            mode="normal",
            memory_count=2,
            char_count=321,
            request_fields=("system_prompt", "messages"),
            scope_fields=("event.get_sender_id", "event.unified_msg_origin"),
            message_type="friendmessage",
            session_type="friendmessage",
            fragment="secret memory content owner-1 /root/hidden prompt",
        )

        summary = format_dry_run_log_summary(result)

        self.assertEqual(
            summary,
            "yushu_live_injection_dry_run skip_reason= mode=normal memory_count=2 char_count=321 fields=system_prompt,messages message_type=friendmessage session_type=friendmessage source_fields=event.get_sender_id,event.unified_msg_origin",
        )
        self.assertNotIn("secret memory content", summary)
        self.assertNotIn("owner-1", summary)
        self.assertNotIn("/root/", summary)
        self.assertNotIn("prompt ", summary)

    def test_live_apply_disabled_result_does_not_modify_request(self) -> None:
        request = DummyRequest()
        result = LiveInjectionDryRunResult(
            should_inject=False,
            skip_reason="prompt_injection_disabled",
            mode="skip",
            memory_count=0,
            char_count=0,
            request_fields=("system_prompt", "prompt"),
        )

        applied = apply_live_injection_to_system_prompt(request, result)

        self.assertFalse(applied)
        self.assertEqual(request.system_prompt, "base system")
        self.assertEqual(request.prompt, "base prompt")

    def test_live_apply_owner_normal_appends_system_prompt_only(self) -> None:
        request = DummyRequest()
        result = LiveInjectionDryRunResult(
            should_inject=True,
            skip_reason="",
            mode="normal",
            memory_count=1,
            char_count=20,
            request_fields=("system_prompt", "prompt"),
            fragment="[YUSHU_OWNER_PRIVATE_CONTEXT]",
        )

        applied = apply_live_injection_to_system_prompt(request, result)

        self.assertTrue(applied)
        self.assertEqual(
            request.system_prompt,
            "base system\n\n[YUSHU_OWNER_PRIVATE_CONTEXT]",
        )
        self.assertEqual(request.prompt, "base prompt")

    def test_live_apply_missing_system_prompt_fail_closed(self) -> None:
        request = RequestWithoutSystemPrompt()
        result = LiveInjectionDryRunResult(
            should_inject=True,
            skip_reason="",
            mode="normal",
            memory_count=0,
            char_count=20,
            request_fields=("prompt",),
            fragment="[YUSHU_OWNER_PRIVATE_CONTEXT]",
        )

        with self.assertRaises(LiveInjectionError):
            apply_live_injection_to_system_prompt(request, result)

        self.assertEqual(request.prompt, "base prompt")

    def test_live_apply_readonly_system_prompt_fail_closed(self) -> None:
        request = ReadOnlySystemPromptRequest()
        result = LiveInjectionDryRunResult(
            should_inject=True,
            skip_reason="",
            mode="normal",
            memory_count=0,
            char_count=20,
            request_fields=("system_prompt", "prompt"),
            fragment="[YUSHU_OWNER_PRIVATE_CONTEXT]",
        )

        with self.assertRaises(LiveInjectionError):
            apply_live_injection_to_system_prompt(request, result)

        self.assertEqual(request.prompt, "base prompt")

    def test_live_apply_non_owner_or_group_skip_does_not_modify_request(self) -> None:
        request = DummyRequest()
        result = LiveInjectionDryRunResult(
            should_inject=False,
            skip_reason="not_owner",
            mode="skip",
            memory_count=0,
            char_count=0,
            request_fields=("system_prompt", "prompt"),
            fragment="[YUSHU_OWNER_PRIVATE_CONTEXT]",
        )

        applied = apply_live_injection_to_system_prompt(request, result)

        self.assertFalse(applied)
        self.assertEqual(request.system_prompt, "base system")
        self.assertEqual(request.prompt, "base prompt")

    def test_group_message_prompt_enabled_still_skips_and_does_not_modify_request(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "preference", "喜欢短句")
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(
                    sender_id="owner-1",
                    message_type="MessageType.GROUP_MESSAGE",
                    session_id="default:GroupMessage:10001",
                ),
                request,
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "owner_user_ids": ["owner-1"],
                },
            )
            applied = apply_live_injection_to_system_prompt(request, result)

            self.assertFalse(result.should_inject)
            self.assertEqual(result.skip_reason, "not_private")
            self.assertEqual(result.mode, "skip")
            self.assertEqual(result.memory_count, 0)
            self.assertFalse(applied)
            self.assertEqual(request.system_prompt, "base system")
            self.assertEqual(request.prompt, "base prompt")

    def test_group_review_request_still_skips_and_does_not_modify_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(
                    sender_id="owner-1",
                    message_type="GroupMessage",
                    session_id="default:GroupMessage:10001",
                    message="帮我复盘一下",
                ),
                request,
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "owner_user_ids": ["owner-1"],
                },
            )
            applied = apply_live_injection_to_system_prompt(request, result)

            self.assertFalse(result.should_inject)
            self.assertEqual(result.skip_reason, "not_private")
            self.assertFalse(applied)
            self.assertEqual(request.system_prompt, "base system")
            self.assertEqual(request.prompt, "base prompt")

    def test_owner_review_request_uses_coach_and_appends_system_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            store.add_memory("owner-1", "private", "s1", "preference", "喜欢短句")
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(message="帮我复盘一下刚才哪里不对"),
                request,
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "owner_user_ids": ["owner-1"],
                },
            )
            applied = apply_live_injection_to_system_prompt(request, result)

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "coach")
            self.assertEqual(result.memory_count, 1)
            self.assertIn("[YUSHU_COACH_REVIEW_CONTEXT]", result.fragment)
            self.assertTrue(applied)
            self.assertTrue(request.system_prompt.startswith("base system\n\n"))
            self.assertIn("[YUSHU_COACH_REVIEW_CONTEXT]", request.system_prompt)
            self.assertIn("复盘内容只作为当轮建议", request.system_prompt)
            self.assertEqual(request.prompt, "base prompt")

    def test_custom_coach_review_trigger_keyword_enters_coach_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            result = build_live_injection_dry_run(
                DummyEvent(message="帮我拆一下这句话"),
                DummyRequest(),
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "coach_review_trigger_keywords": ["拆一下"],
                    "owner_user_ids": ["owner-1"],
                },
            )

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "coach")

    def test_custom_coach_review_exit_keyword_forces_normal_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            result = build_live_injection_dry_run(
                DummyEvent(message="别点评了，帮我复盘一下"),
                DummyRequest(),
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "coach_review_trigger_keywords": ["复盘"],
                    "coach_review_exit_keywords": [" 别点评了 "],
                    "owner_user_ids": ["owner-1"],
                },
            )

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "normal")

    def test_bad_or_empty_keyword_config_falls_back_to_defaults(self) -> None:
        bad_config = {
            "coach_review_trigger_keywords": "复盘",
            "coach_review_exit_keywords": {"正常聊": True},
        }

        self.assertIn("复盘", get_coach_review_trigger_keywords(bad_config))
        self.assertIn("正常聊", get_coach_review_exit_keywords(bad_config))

        normalized = get_coach_review_trigger_keywords(
            {"coach_review_trigger_keywords": ["  自定义  ", "", "自定义"]}
        )
        self.assertEqual(normalized, ["自定义"])

        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            result = build_live_injection_dry_run(
                DummyEvent(message="帮我复盘一下"),
                DummyRequest(),
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": True,
                    "coach_review_trigger_keywords": "复盘",
                    "coach_review_exit_keywords": None,
                    "owner_user_ids": ["owner-1"],
                },
            )
            self.assertEqual(result.mode, "coach")

    def test_keyword_summary_is_short(self) -> None:
        summary = summarize_keywords(["复盘", "分析", "哪里不对", "帮我改"])

        self.assertEqual(summary, "复盘, 分析, 哪里不对...")

    def test_conf_schema_has_keyword_fields_and_valid_json(self) -> None:
        schema = json.loads(Path("_conf_schema.json").read_text(encoding="utf-8"))

        self.assertEqual(schema["coach_review_no_history_enabled"]["type"], "bool")
        self.assertIs(schema["coach_review_no_history_enabled"]["default"], True)
        self.assertEqual(
            schema["coach_review_trigger_keywords"]["default"],
            ["复盘", "分析", "哪里不对", "帮我改", "评分", "现实里怎么练"],
        )
        self.assertEqual(
            schema["coach_review_exit_keywords"]["default"],
            ["正常聊", "别复盘了", "继续角色内"],
        )

    def test_conf_schema_user_facing_copy_has_no_stage_language_and_keeps_contract(self) -> None:
        schema_text = Path("_conf_schema.json").read_text(encoding="utf-8")
        schema = json.loads(schema_text)

        expected_contract = {
            "yushu_private_enabled": ("bool", True),
            "group_light_mode": ("bool", True),
            "yushu_group_enabled": ("bool", False),
            "owner_user_ids": ("list", []),
            "memory_mode": ("string", "suggest"),
            "memory_enabled": ("bool", True),
            "memory_allow_manual_add": ("bool", True),
            "memory_allow_export": ("bool", True),
            "memory_allow_group_rule": ("bool", False),
            "memory_private_only": ("bool", True),
            "coach_review_owner_only": ("bool", True),
            "proactive_private_only": ("bool", True),
            "proactive_enabled": ("bool", False),
            "proactive_daily_limit": ("int", 1),
            "proactive_pause_hours": ("int", 24),
            "max_memory_per_user": ("int", 50),
            "max_pinned_memory_per_user": ("int", 15),
            "memory_db_limit_mb": ("int", 2),
            "memory_exports_limit_mb": ("int", 2),
            "memory_total_limit_mb": ("int", 4),
            "memory_export_file_limit_kb": ("int", 512),
            "memory_content_max_chars": ("int", 500),
            "memory_auto_prune_enabled": ("bool", False),
            "prompt_injection_enabled": ("bool", False),
            "memory_injection_enabled": ("bool", False),
            "state_machine_enabled": ("bool", False),
            "coach_review_enabled": ("bool", True),
            "coach_review_no_history_enabled": ("bool", True),
            "coach_review_trigger_keywords": (
                "list",
                ["复盘", "分析", "哪里不对", "帮我改", "评分", "现实里怎么练"],
            ),
            "coach_review_exit_keywords": ("list", ["正常聊", "别复盘了", "继续角色内"]),
            "max_injected_memories": ("int", 6),
            "memory_injection_char_budget": ("int", 900),
            "include_pinned_memories": ("bool", True),
            "include_open_threads": ("bool", True),
            "voicebook_enabled": ("bool", True),
            "eval_enabled": ("bool", False),
            "debug_mode": ("bool", False),
            "proactive_chat_integration_enabled": ("bool", False),
            "spectrecore_integration_enabled": ("bool", False),
        }
        self.assertEqual(set(schema), set(expected_contract))
        for key, (expected_type, expected_default) in expected_contract.items():
            self.assertEqual(schema[key]["type"], expected_type)
            self.assertEqual(schema[key]["default"], expected_default)

        for banned in ["第三阶段", "第四阶段", "Stage 5A", "阶段默认", "仅显示配置状态"]:
            self.assertNotIn(banned, schema_text)

        for key in [
            "yushu_private_enabled",
            "group_light_mode",
            "prompt_injection_enabled",
            "memory_injection_enabled",
            "coach_review_enabled",
            "coach_review_no_history_enabled",
            "debug_mode",
        ]:
            item_text = json.dumps(schema[key], ensure_ascii=False)
            self.assertRegex(item_text, r"推荐开启|推荐关闭|建议关闭|不注入群聊")

    def test_owner_normal_chat_phrases_force_normal_mode(self) -> None:
        phrases = ["正常聊", "别复盘了", "继续角色内"]
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    request = DummyRequest()
                    result = build_live_injection_dry_run(
                        DummyEvent(message=phrase),
                        request,
                        store,
                        {
                            "prompt_injection_enabled": True,
                            "memory_injection_enabled": True,
                            "coach_review_enabled": True,
                            "owner_user_ids": ["owner-1"],
                        },
                    )
                    applied = apply_live_injection_to_system_prompt(request, result)

                    self.assertTrue(result.should_inject)
                    self.assertEqual(result.mode, "normal")
                    self.assertIn("[YUSHU_OWNER_PRIVATE_CONTEXT]", result.fragment)
                    self.assertTrue(applied)
                    self.assertEqual(request.prompt, "base prompt")

    def test_coach_review_disabled_keeps_trigger_words_in_normal_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = self._store(Path(td))
            request = DummyRequest()

            result = build_live_injection_dry_run(
                DummyEvent(message="帮我复盘一下"),
                request,
                store,
                {
                    "prompt_injection_enabled": True,
                    "memory_injection_enabled": True,
                    "coach_review_enabled": False,
                    "owner_user_ids": ["owner-1"],
                },
            )
            applied = apply_live_injection_to_system_prompt(request, result)

            self.assertTrue(result.should_inject)
            self.assertEqual(result.mode, "normal")
            self.assertIn("[YUSHU_OWNER_PRIVATE_CONTEXT]", result.fragment)
            self.assertTrue(applied)
            self.assertEqual(request.prompt, "base prompt")

    def test_live_apply_coach_fragment_appends_system_prompt_only(self) -> None:
        request = DummyRequest()
        result = LiveInjectionDryRunResult(
            should_inject=True,
            skip_reason="",
            mode="coach",
            memory_count=1,
            char_count=20,
            request_fields=("system_prompt", "prompt"),
            fragment="[YUSHU_COACH_REVIEW_CONTEXT]",
        )

        applied = apply_live_injection_to_system_prompt(request, result)

        self.assertTrue(applied)
        self.assertEqual(
            request.system_prompt,
            "base system\n\n[YUSHU_COACH_REVIEW_CONTEXT]",
        )
        self.assertEqual(request.prompt, "base prompt")

    def test_applied_log_summary_uses_only_allowed_fields(self) -> None:
        result = LiveInjectionDryRunResult(
            should_inject=True,
            skip_reason="",
            mode="normal",
            memory_count=1,
            char_count=251,
            request_fields=("system_prompt", "prompt"),
            fragment="secret memory owner-1 /root/path",
        )

        summary = format_applied_log_summary(result)

        self.assertEqual(
            summary,
            "yushu_live_injection_applied mode=normal memory_count=1 char_count=251 target=system_prompt",
        )
        self.assertNotIn("secret", summary)
        self.assertNotIn("owner-1", summary)
        self.assertNotIn("/root/", summary)


if __name__ == "__main__":
    unittest.main()
