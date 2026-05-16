"""Minimal yushu_core plugin command surface.

Stage 5B adds a disabled/dry-run LLM request hook. It does not inject prompts,
call models, call proactive_chat, call SpectreCore, or automatically write
memory.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from astrbot.api import logger
from astrbot.api.all import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.core.star.filter.command import GreedyStr

from .core.console_overview import build_console_overview_status
from .core.command_format import (
    config_audit_report,
    config_diff_report,
    format_yushu_help,
    format_memory_command_status,
    format_memory_export,
    format_memory_list,
    format_memory_prune,
    format_memory_view,
)
from .core.eval_runner import summarize_eval_cases
from .core.memory_console import (
    build_memory_console_snapshot,
    delete_memory_console_item,
    edit_memory_console_item,
    export_memory_console_scope,
    pin_memory_console_item,
    prune_memory_console_confirm,
    prune_memory_console_dry_run,
    render_memory_console_html,
)
from .core.live_injection import (
    apply_live_injection_to_system_prompt,
    build_live_injection_dry_run,
    format_applied_log_summary,
    format_dry_run_log_summary,
)
from .core.memory_injection import build_memory_injection
from .core.memory_store import (
    ALLOWED_MEMORY_TYPES,
    MemoryLimits,
    MemoryStore,
    MemoryStoreError,
    contains_sensitive_field,
)
from .core.memory_types import (
    memory_type_display,
    memory_type_help_text,
    memory_type_inline_help,
    normalize_memory_type,
)
from .core.mvp_doctor import build_doctor_report
from .core.prompt_fragments import (
    build_coach_review_fragment,
    build_group_light_fragment,
    build_owner_private_fragment,
    build_proactive_fragment_design_only,
)
from .core.scope import is_owner
from .core.yushu_state import (
    DEFAULT_YUSHU_STATE,
    get_coach_review_exit_keywords,
    get_coach_review_trigger_keywords,
    normalize_state,
    summarize_keywords,
)


def _get_bool(config: dict[str, Any], key: str, default: bool = False) -> bool:
    return bool(config.get(key, default))


def _owner_count(config: dict[str, Any]) -> int:
    owners = config.get("owner_user_ids", [])
    if not isinstance(owners, list):
        return 0
    return len([item for item in owners if str(item or "").strip()])


def _owners(config: dict[str, Any]) -> list[str]:
    owners = config.get("owner_user_ids", [])
    if not isinstance(owners, list):
        return []
    return [str(item or "").strip() for item in owners if str(item or "").strip()]


def _bytes_label(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f}MB"
    if size >= 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size}B"


def _cn_value(value: Any) -> str:
    if value is True:
        return "已开启"
    if value is False:
        return "已关闭"
    text = str(value if value is not None else "none")
    labels = {
        "none": "无",
        "suggest": "建议保存",
        "manual": "手动保存",
        "off": "已关闭",
        "auto": "自动保存",
        "disabled": "未启用",
        "enabled": "已启用",
    }
    return labels.get(text, text)


def _normalize_memory_type(memory_type: str | None) -> str | None:
    return normalize_memory_type(memory_type)


def _type_help_line() -> str:
    return memory_type_help_text()


def _parse_duration(duration: str) -> datetime | None:
    value = str(duration or "").strip().lower()
    if not value:
        return None
    unit = value[-1]
    amount_text = value[:-1] if unit in {"m", "h", "d"} else value
    try:
        amount = int(amount_text)
    except ValueError:
        return None
    if amount <= 0:
        return None
    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    elif unit.isdigit():
        delta = timedelta(hours=amount)
    else:
        return None
    return datetime.now().astimezone() + delta


def _session_scope(event: AstrMessageEvent) -> str:
    if event.is_private_chat():
        return "private"
    return f"group:{event.get_group_id() or 'unknown'}"


def _memory_scope_for_type(event: AstrMessageEvent, memory_type: str | None = None) -> str:
    if event.is_private_chat():
        return "private"
    if memory_type == "group_rule":
        return _session_scope(event)
    return "private"


@register(
    "yushu_core",
    "local",
    "雨舒关系型沟通陪练系统的最小骨架插件",
    "0.1.0",
    "",
)
class YushuCorePlugin(Star):
    """Owner-only yushu_core command surface."""

    def __init__(self, context: Context, config: dict[str, Any] | None = None):
        super().__init__(context)
        self.config = config or {}
        self._register_memory_console_api()
        self._register_console_overview_api()

    def _register_console_overview_api(self) -> None:
        register_web_api = getattr(self.context, "register_web_api", None)
        if not callable(register_web_api):
            return

        async def console_status() -> dict[str, Any]:
            try:
                result = build_console_overview_status(
                    self._memory_store(),
                    self.config,
                )
                return {"status": "ok", "data": result}
            except Exception as exc:
                logger.info(
                    "yushu_console_status_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "console_status_failed"}

        register_web_api(
            "yushu_core/console/status",
            console_status,
            ["GET"],
            "Read-only yushu_core console status",
        )

    def _register_memory_console_api(self) -> None:
        register_web_api = getattr(self.context, "register_web_api", None)
        if not callable(register_web_api):
            return

        async def memory_console_page() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            args = request.args if request is not None else {}
            snapshot = build_memory_console_snapshot(
                self._memory_store(),
                self.config,
                owner_key=args.get("owner"),
                scope_key=args.get("scope"),
                memory_type=args.get("type"),
                pinned=args.get("pinned"),
                memory_id=args.get("memory_id"),
            )
            return {"status": "ok", "data": snapshot}

        async def memory_console_delete() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = delete_memory_console_item(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                    memory_id=body.get("memory_id"),
                    confirm=body.get("confirm"),
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_delete_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "delete_failed"}

        async def memory_console_edit() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = edit_memory_console_item(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                    memory_id=body.get("memory_id"),
                    memory_type=body.get("type"),
                    content=body.get("content"),
                    confirm=body.get("confirm"),
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_edit_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "edit_failed"}

        async def memory_console_pin() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = pin_memory_console_item(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                    memory_id=body.get("memory_id"),
                    pinned=True,
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_pin_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "pin_failed"}

        async def memory_console_unpin() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = pin_memory_console_item(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                    memory_id=body.get("memory_id"),
                    pinned=False,
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_unpin_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "unpin_failed"}

        async def memory_console_export() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = export_memory_console_scope(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                    export_format=body.get("format"),
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_export_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "export_failed"}

        async def memory_console_prune_dry_run() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = prune_memory_console_dry_run(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_prune_dry_run_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "prune_failed"}

        async def memory_console_prune_confirm() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                result = prune_memory_console_confirm(
                    self._memory_store(),
                    self.config,
                    owner_key=body.get("owner"),
                    scope_key=body.get("scope"),
                    plan_token=body.get("plan_token"),
                )
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_prune_confirm_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "prune_failed"}

        async def memory_console_action() -> dict[str, Any]:
            try:
                from quart import request  # type: ignore
            except Exception:
                request = None

            try:
                body = await request.get_json(silent=True) if request is not None else {}
                if not isinstance(body, dict):
                    body = {}
                action = str(body.get("action") or "").strip()
                if action == "export":
                    result = export_memory_console_scope(
                        self._memory_store(),
                        self.config,
                        owner_key=body.get("owner"),
                        scope_key=body.get("scope"),
                        export_format=body.get("format"),
                    )
                elif action == "prune_dry_run":
                    result = prune_memory_console_dry_run(
                        self._memory_store(),
                        self.config,
                        owner_key=body.get("owner"),
                        scope_key=body.get("scope"),
                    )
                elif action == "prune_confirm":
                    result = prune_memory_console_confirm(
                        self._memory_store(),
                        self.config,
                        owner_key=body.get("owner"),
                        scope_key=body.get("scope"),
                        plan_token=body.get("plan_token"),
                    )
                else:
                    raise MemoryStoreError("invalid_memory_console_action")
                return {"status": "ok", "data": result}
            except MemoryStoreError as exc:
                return {"status": "error", "message": exc.reason}
            except Exception as exc:
                logger.info(
                    "yushu_memory_console_action_fail_closed error_type=%s",
                    type(exc).__name__,
                )
                return {"status": "error", "message": "action_failed"}

        register_web_api(
            "yushu_core/memory-console",
            memory_console_page,
            ["GET"],
            "Read-only memory console",
        )
        register_web_api(
            "yushu_core/memory-console/action",
            memory_console_action,
            ["POST"],
            "Run selected yushu_core memory console action",
        )
        register_web_api(
            "yushu_core/memory-console/delete",
            memory_console_delete,
            ["POST"],
            "Delete one yushu_core memory",
        )
        register_web_api(
            "yushu_core/memory-console/edit",
            memory_console_edit,
            ["POST"],
            "Edit one yushu_core memory",
        )
        register_web_api(
            "yushu_core/memory-console/pin",
            memory_console_pin,
            ["POST"],
            "Pin one yushu_core memory",
        )
        register_web_api(
            "yushu_core/memory-console/unpin",
            memory_console_unpin,
            ["POST"],
            "Unpin one yushu_core memory",
        )
        register_web_api(
            "yushu_core/memory-console/export",
            memory_console_export,
            ["POST"],
            "Export selected yushu_core memories",
        )
        register_web_api(
            "yushu_core/memory-console/prune-dry-run",
            memory_console_prune_dry_run,
            ["POST"],
            "Preview yushu_core memory prune",
        )
        register_web_api(
            "yushu_core/memory-console/prune-confirm",
            memory_console_prune_confirm,
            ["POST"],
            "Confirm yushu_core memory prune",
        )

    @filter.on_llm_request()
    async def yushu_live_injection_dry_run(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ):
        """Stage 5B disabled/dry-run hook; never mutates ProviderRequest."""

        try:
            result = build_live_injection_dry_run(
                event,
                req,
                self._memory_store(),
                self.config,
            )
        except Exception as exc:
            if _get_bool(self.config, "debug_mode", False):
                logger.info(
                    "yushu_live_injection_fail_closed error_type=%s",
                    type(exc).__name__,
                )
            return

        debug_mode = _get_bool(self.config, "debug_mode", False)
        if debug_mode:
            logger.info(format_dry_run_log_summary(result))
        try:
            applied = apply_live_injection_to_system_prompt(req, result)
        except Exception as exc:
            logger.info(
                "yushu_live_injection_fail_closed error_type=%s",
                type(exc).__name__,
            )
            return
        if applied and debug_mode:
            logger.info(format_applied_log_summary(result))

    @filter.command_group("ys")
    def ys(self):
        """雨舒 core 命令组。"""
        pass

    @ys.command("status")
    async def status(self, event: AstrMessageEvent):
        """Show read-only yushu_core skeleton status."""

        eval_summary = summarize_eval_cases()
        lines = [
            "雨舒状态",
            "阶段：stage3_skeleton",
            f"私聊雨舒：{_cn_value(_get_bool(self.config, 'yushu_private_enabled', True))}",
            f"群聊轻量模式：{_cn_value(_get_bool(self.config, 'group_light_mode', True))}",
            f"群聊雨舒能力：{_cn_value(_get_bool(self.config, 'yushu_group_enabled', False))}",
            f"提示词注入：{_cn_value(_get_bool(self.config, 'prompt_injection_enabled', False))}",
            f"记忆模式：{_cn_value(self.config.get('memory_mode', 'suggest'))}",
            f"记忆运行状态：{_cn_value(_get_bool(self.config, 'memory_enabled', True))}",
            f"主动消息：{_cn_value(_get_bool(self.config, 'proactive_enabled', False))}",
            f"评估模式：{_cn_value(_get_bool(self.config, 'eval_enabled', False))}",
            f"Owner 数量：{_owner_count(self.config)}",
            f"评估用例数量：{eval_summary.get('case_count', 0)}",
            "主动接管：未启用",
            "记忆写入：手动保存",
        ]
        yield event.plain_result("\n".join(lines))

    @ys.command("doctor")
    async def doctor(self, event: AstrMessageEvent):
        """Run a read-only MVP readiness check without exposing identifiers."""

        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None
        yield event.plain_result(
            build_doctor_report(
                config=self.config,
                store=self._memory_store(),
                owner_id=user_id,
                eval_summary=summarize_eval_cases(),
            )
        )

    @ys.command("help")
    async def help(self, event: AstrMessageEvent):
        """Show short Chinese command help."""

        yield event.plain_result(format_yushu_help())

    @ys.group("memory")
    def memory(self):
        """雨舒手动记忆命令组。"""
        pass

    def _memory_store(self) -> MemoryStore:
        return MemoryStore(limits=MemoryLimits.from_config(self.config))

    def _owner_user_id(self, event: AstrMessageEvent) -> str | None:
        user_id = str(event.get_sender_id() or "").strip()
        if not is_owner(user_id, _owners(self.config)):
            return None
        return user_id

    def _write_allowed(self, store: MemoryStore, user_id: str) -> str | None:
        if not _get_bool(self.config, "memory_enabled", True):
            return "memory_disabled"
        flag = store.get_runtime_flag(user_id)
        if not flag.get("enabled", True):
            return "memory_off"
        paused_until = str(flag.get("paused_until") or "").strip()
        if paused_until:
            try:
                paused_until_dt = datetime.fromisoformat(paused_until)
            except ValueError:
                return f"memory_paused_until: {paused_until}"
            if paused_until_dt > datetime.now().astimezone():
                return f"memory_paused_until: {paused_until}"
        return None

    def _require_owner_result(
        self,
        event: AstrMessageEvent,
    ) -> tuple[str | None, Any | None]:
        user_id = self._owner_user_id(event)
        if user_id is None:
            return None, event.plain_result("permission_denied: owner only")
        return user_id, None

    @memory.command("status")
    async def memory_status(self, event: AstrMessageEvent):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        scope = _session_scope(event)
        store = self._memory_store()
        status = store.status(user_id, scope)
        flag = store.get_runtime_flag(user_id)
        lines = [
            "雨舒记忆状态",
            f"记忆模式：{_cn_value(self.config.get('memory_mode', 'suggest'))}",
            f"记忆运行状态：{_cn_value(_get_bool(self.config, 'memory_enabled', True))}",
            f"运行时状态：{_cn_value(bool(flag.get('enabled', True)))}",
            f"暂停到：{_cn_value(flag.get('paused_until') or 'none')}",
            f"Owner 数量：{_owner_count(self.config)}",
            f"范围：{scope}",
            f"数据库存在：{_cn_value(status['db_exists'])}",
            f"记忆条数：{status['memory_count']}",
            f"置顶条数：{status['pinned_count']}",
            f"数据库大小：{_bytes_label(status['db_size_bytes'])}",
            f"导出文件大小：{_bytes_label(status['exports_size_bytes'])}",
            f"总占用：{_bytes_label(status['total_size_bytes'])}",
            f"数据库上限：{_bytes_label(status['db_limit_bytes'])}",
            f"导出上限：{_bytes_label(status['exports_limit_bytes'])}",
            f"总上限：{_bytes_label(status['total_limit_bytes'])}",
            memory_type_inline_help(),
        ]
        yield event.plain_result("\n".join(lines))

    @memory.command("list")
    async def memory_list(
        self,
        event: AstrMessageEvent,
        memory_type: str | None = None,
    ):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        raw_memory_type = str(memory_type or "").strip()
        memory_type = _normalize_memory_type(raw_memory_type)
        if raw_memory_type and memory_type is None:
            yield event.plain_result(
                format_memory_command_status("invalid_memory_type") + "\n" + _type_help_line()
            )
            return
        scope = _memory_scope_for_type(event, memory_type)
        items = self._memory_store().list_memories(user_id, scope, memory_type)
        if not items:
            yield event.plain_result(format_memory_command_status("memory_empty"))
            return
        yield event.plain_result(format_memory_list(items))

    @memory.command("view")
    async def memory_view(self, event: AstrMessageEvent, memory_id: str):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        try:
            item = self._memory_store().get_memory(
                user_id,
                _session_scope(event),
                str(memory_id or "").strip(),
            )
        except MemoryStoreError:
            yield event.plain_result(format_memory_command_status("memory_not_found"))
            return
        yield event.plain_result(format_memory_view(item))

    @memory.command("add")
    async def memory_add(
        self,
        event: AstrMessageEvent,
        memory_type: str,
        content: GreedyStr,
    ):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        store = self._memory_store()
        blocked = self._write_allowed(store, user_id)
        if blocked:
            yield event.plain_result(format_memory_command_status(blocked))
            return
        if not _get_bool(self.config, "memory_allow_manual_add", True):
            yield event.plain_result(format_memory_command_status("manual_add_disabled"))
            return
        raw_memory_type = str(memory_type or "").strip()
        memory_type = _normalize_memory_type(raw_memory_type)
        if memory_type is None:
            yield event.plain_result(
                format_memory_command_status("invalid_memory_type") + "\n" + _type_help_line()
            )
            return
        if not event.is_private_chat() and memory_type != "group_rule":
            yield event.plain_result(format_memory_command_status("group_memory_requires_group_rule"))
            return
        if memory_type == "group_rule" and not _get_bool(
            self.config,
            "memory_allow_group_rule",
            False,
        ):
            yield event.plain_result(format_memory_command_status("group_rule_disabled"))
            return
        scope = _memory_scope_for_type(event, memory_type)
        try:
            item = store.add_memory(
                user_id=user_id,
                scope=scope,
                session_id=str(event.unified_msg_origin or ""),
                memory_type=memory_type,
                content=str(content or ""),
            )
        except MemoryStoreError as exc:
            yield event.plain_result(format_memory_command_status(exc.reason))
            return
        yield event.plain_result(
            "\n".join(
                [
                    format_memory_command_status("memory_added", item.get("id")),
                    f"类型：{memory_type_display(str(item.get('type') or ''))}",
                ]
            )
        )

    @memory.command("edit")
    async def memory_edit(
        self,
        event: AstrMessageEvent,
        memory_id: str,
        content: GreedyStr,
    ):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        store = self._memory_store()
        blocked = self._write_allowed(store, user_id)
        if blocked:
            yield event.plain_result(format_memory_command_status(blocked))
            return
        try:
            item = store.edit_memory(
                user_id,
                _session_scope(event),
                str(memory_id or "").strip(),
                str(content or ""),
            )
        except MemoryStoreError as exc:
            yield event.plain_result(format_memory_command_status(exc.reason))
            return
        yield event.plain_result(format_memory_command_status("memory_edited", item.get("id")))

    @memory.command("delete")
    async def memory_delete(self, event: AstrMessageEvent, memory_id: str):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        store = self._memory_store()
        blocked = self._write_allowed(store, user_id)
        if blocked:
            yield event.plain_result(format_memory_command_status(blocked))
            return
        try:
            store.delete_memory(user_id, _session_scope(event), str(memory_id or "").strip())
        except MemoryStoreError as exc:
            yield event.plain_result(format_memory_command_status(exc.reason))
            return
        yield event.plain_result(format_memory_command_status("memory_deleted"))

    @memory.command("clear")
    async def memory_clear(
        self,
        event: AstrMessageEvent,
        scope_name: str,
        confirm: str | None = None,
    ):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        store = self._memory_store()
        blocked = self._write_allowed(store, user_id)
        if blocked:
            yield event.plain_result(format_memory_command_status(blocked))
            return
        if scope_name != "private" or confirm != "confirm":
            yield event.plain_result("usage: /ys memory clear private confirm")
            return
        deleted = store.clear_private(user_id)
        yield event.plain_result(format_memory_command_status("memory_cleared_private", deleted))

    @memory.command("pin")
    async def memory_pin(self, event: AstrMessageEvent, memory_id: str):
        async for result in self._memory_set_pin(event, memory_id, True):
            yield result

    @memory.command("unpin")
    async def memory_unpin(self, event: AstrMessageEvent, memory_id: str):
        async for result in self._memory_set_pin(event, memory_id, False):
            yield result

    async def _memory_set_pin(
        self,
        event: AstrMessageEvent,
        memory_id: str,
        pinned: bool,
    ):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        store = self._memory_store()
        blocked = self._write_allowed(store, user_id)
        if blocked:
            yield event.plain_result(format_memory_command_status(blocked))
            return
        try:
            if pinned:
                current = store.get_memory(
                    user_id,
                    _session_scope(event),
                    str(memory_id or "").strip(),
                )
                if contains_sensitive_field(current.get("content")):
                    yield event.plain_result(format_memory_command_status("sensitive_content"))
                    return
            item = store.set_pinned(
                user_id,
                _session_scope(event),
                str(memory_id or "").strip(),
                pinned,
            )
        except MemoryStoreError as exc:
            yield event.plain_result(format_memory_command_status(exc.reason))
            return
        action = "memory_pinned" if pinned else "memory_unpinned"
        yield event.plain_result(format_memory_command_status(action, item.get("id")))

    @memory.command("export")
    async def memory_export(
        self,
        event: AstrMessageEvent,
        export_format: str = "md",
    ):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        if not _get_bool(self.config, "memory_allow_export", True):
            yield event.plain_result(format_memory_command_status("export_disabled"))
            return
        try:
            result = self._memory_store().export_memories(
                user_id,
                _session_scope(event),
                export_format,
            )
        except MemoryStoreError as exc:
            yield event.plain_result(format_memory_command_status(exc.reason))
            return
        yield event.plain_result(
            format_memory_export(result, _bytes_label(int(result.get("size_bytes") or 0)))
        )

    @memory.command("prune")
    async def memory_prune(self, event: AstrMessageEvent, mode: str):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        if mode not in {"dry-run", "confirm"}:
            yield event.plain_result("usage: /ys memory prune dry-run|confirm")
            return
        store = self._memory_store()
        blocked = self._write_allowed(store, user_id)
        if blocked and mode == "confirm":
            yield event.plain_result(format_memory_command_status(blocked))
            return
        result = store.prune(user_id, _session_scope(event), confirm=(mode == "confirm"))
        yield event.plain_result(
            format_memory_prune(mode, result, _bytes_label(int(result.get("planned_bytes") or 0)))
        )

    @memory.command("off")
    async def memory_off(self, event: AstrMessageEvent):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None
        self._memory_store().set_runtime_flag(user_id, enabled=False)
        yield event.plain_result(format_memory_command_status("memory_off"))

    @memory.command("on")
    async def memory_on(self, event: AstrMessageEvent):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None
        self._memory_store().set_runtime_flag(user_id, enabled=True, paused_until=None)
        yield event.plain_result(format_memory_command_status("memory_on"))

    @memory.command("pause")
    async def memory_pause(self, event: AstrMessageEvent, duration: str):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        assert user_id is not None

        paused_until = _parse_duration(duration)
        if paused_until is None:
            yield event.plain_result(format_memory_command_status("invalid_duration"))
            return
        paused_text = paused_until.isoformat(timespec="seconds")
        self._memory_store().set_runtime_flag(
            user_id,
            enabled=True,
            paused_until=paused_text,
        )
        yield event.plain_result(format_memory_command_status(f"memory_paused_until: {paused_text}"))

    @ys.group("config")
    def config_commands(self):
        """雨舒配置检查命令组。"""
        pass

    @config_commands.command("audit")
    async def config_audit(self, event: AstrMessageEvent):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        yield event.plain_result(config_audit_report(self.config))

    @config_commands.command("diff")
    async def config_diff(self, event: AstrMessageEvent):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        yield event.plain_result(config_diff_report(self.config))

    @ys.group("injection")
    def injection(self):
        """Stage 5A prompt preview commands."""
        pass

    @injection.command("status")
    async def injection_status(self, event: AstrMessageEvent):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return
        store = self._memory_store()
        runtime = store.get_runtime_flag(user_id)
        trigger_keywords = get_coach_review_trigger_keywords(self.config)
        exit_keywords = get_coach_review_exit_keywords(self.config)
        lines = [
            "雨舒注入状态",
            f"提示词注入：{_cn_value(_get_bool(self.config, 'prompt_injection_enabled', False))}",
            f"记忆注入：{_cn_value(_get_bool(self.config, 'memory_injection_enabled', False))}",
            f"状态机：{_cn_value(_get_bool(self.config, 'state_machine_enabled', False))}",
            f"复盘模式：{_cn_value(_get_bool(self.config, 'coach_review_enabled', True))}",
            f"复盘触发词数量：{len(trigger_keywords)}",
            f"复盘触发词：{summarize_keywords(trigger_keywords)}",
            f"复盘退出词数量：{len(exit_keywords)}",
            f"复盘退出词：{summarize_keywords(exit_keywords)}",
            f"记忆运行状态：{_cn_value(bool(runtime.get('enabled', True)))}",
            f"暂停到：{_cn_value(runtime.get('paused_until') or 'none')}",
            f"单轮注入记忆上限：{int(self.config.get('max_injected_memories', 6) or 6)}",
            f"记忆注入字符预算：{int(self.config.get('memory_injection_char_budget', 900) or 900)}",
            f"包含置顶记忆：{_cn_value(_get_bool(self.config, 'include_pinned_memories', True))}",
            f"包含未结话题：{_cn_value(_get_bool(self.config, 'include_open_threads', True))}",
        ]
        yield event.plain_result("\n".join(lines))

    @injection.command("preview")
    async def injection_preview(self, event: AstrMessageEvent, mode: str):
        user_id, denied = self._require_owner_result(event)
        if denied:
            yield denied
            return

        mode = str(mode or "").strip().lower()
        store = self._memory_store()
        injected = build_memory_injection(store, user_id, self.config)
        state = normalize_state(DEFAULT_YUSHU_STATE)
        if mode == "normal":
            fragment = build_owner_private_fragment(injected["items"], state)
        elif mode == "coach":
            fragment = build_coach_review_fragment(injected["items"], state)
        elif mode == "group":
            fragment = build_group_light_fragment()
        elif mode == "proactive":
            fragment = build_proactive_fragment_design_only()
        else:
            yield event.plain_result("usage: /ys injection preview normal|coach|group")
            return

        lines = [
            "雨舒注入预览",
            f"模式：{ {'normal': '角色内', 'coach': '复盘', 'group': '群聊轻量', 'proactive': '设计说明'}[mode] }",
            f"直播注入：{_get_bool(self.config, 'prompt_injection_enabled', False)}",
            f"记忆注入：{_get_bool(self.config, 'memory_injection_enabled', False)}",
            f"状态机：{_get_bool(self.config, 'state_machine_enabled', False)}",
            f"复盘功能：{_get_bool(self.config, 'coach_review_enabled', True)}",
            f"预览记忆条数：{len(injected['items'])}",
            "",
            fragment,
        ]
        yield event.plain_result("\n".join(lines))
