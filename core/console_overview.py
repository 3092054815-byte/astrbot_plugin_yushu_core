"""Read-only Yushu Console overview helpers."""

from __future__ import annotations

from typing import Any

from .command_format import get_help_commands, memory_type_short_help
from .memory_console import (
    _bytes_label,
    _owner_details,
    _owners,
    _private_memory_counts,
    memory_type_help_items,
)
from .memory_store import MemoryStore
from .yushu_state import (
    get_coach_review_exit_keywords,
    get_coach_review_trigger_keywords,
)


PLUGIN_VERSION = "0.1.0"


def _bool(config: dict[str, Any] | None, key: str, default: bool = False) -> bool:
    return bool((config or {}).get(key, default))


def _owner_selection(store: MemoryStore, config: dict[str, Any] | None) -> dict[str, Any]:
    owner_ids = _owners(config)
    owner_labels = [f"owner_{index + 1}" for index in range(len(owner_ids))]
    private_counts = _private_memory_counts(store, owner_ids)
    details = _owner_details(owner_labels, owner_ids, private_counts)
    selected_index = 0
    if private_counts:
        best_count = max(private_counts)
        selected_index = private_counts.index(best_count) if best_count > 0 else 0
    selected_key = owner_labels[selected_index] if owner_labels else "owner_none"
    selected_hint = (
        details[selected_index]["label"] if details else "Owner none（未配置）"
    )
    selected_owner_id = owner_ids[selected_index] if owner_ids else ""
    return {
        "owner_ids": owner_ids,
        "selected_owner_id": selected_owner_id,
        "owner_count": len(owner_ids),
        "selected_owner": selected_key,
        "selected_owner_hint": selected_hint,
        "owner_options": details,
    }


def _memory_summary(
    store: MemoryStore,
    config: dict[str, Any] | None,
    owner_id: str,
) -> dict[str, Any]:
    scope = "private"
    status = store.status(owner_id, scope) if owner_id else store.status("", scope)
    flag = store.get_runtime_flag(owner_id) if owner_id else {
        "enabled": True,
        "paused_until": None,
    }
    paused_until = str(flag.get("paused_until") or "").strip() or "none"
    return {
        "scope": "private",
        "total_size_bytes": int(status.get("total_size_bytes") or 0),
        "total_limit_bytes": int(status.get("total_limit_bytes") or 0),
        "memory_mode": str((config or {}).get("memory_mode", "suggest")),
        "memory_enabled": _bool(config, "memory_enabled", True),
        "runtime_enabled": bool(flag.get("enabled", True)),
        "paused_until": paused_until,
        "memory_count": int(status.get("memory_count") or 0),
        "pinned_count": int(status.get("pinned_count") or 0),
        "db_size": _bytes_label(int(status.get("db_size_bytes") or 0)),
        "exports_size": _bytes_label(int(status.get("exports_size_bytes") or 0)),
        "total_size": _bytes_label(int(status.get("total_size_bytes") or 0)),
        "db_limit": _bytes_label(int(status.get("db_limit_bytes") or 0)),
        "exports_limit": _bytes_label(int(status.get("exports_limit_bytes") or 0)),
        "total_limit": _bytes_label(int(status.get("total_limit_bytes") or 0)),
    }


def _health_checks(
    switches: dict[str, bool],
    memory: dict[str, Any],
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if switches.get("debug_mode"):
        checks.append(
            {
                "status": "建议",
                "item": "调试模式",
                "message": "建议关闭调试模式，避免日志过多",
            }
        )
    if switches.get("yushu_group_enabled"):
        checks.append(
            {
                "status": "注意",
                "item": "群聊雨舒能力",
                "message": "群聊雨舒能力已开启，请确认不会启用私聊陪练",
            }
        )
    if switches.get("prompt_injection_enabled") and not switches.get("memory_injection_enabled"):
        checks.append(
            {
                "status": "注意",
                "item": "记忆注入",
                "message": "提示词注入开启，但记忆注入关闭",
            }
        )
    if not switches.get("prompt_injection_enabled"):
        checks.append(
            {
                "status": "注意",
                "item": "live 注入",
                "message": "live 注入未开启，雨舒人格/记忆不会进入真实聊天",
            }
        )
    if not switches.get("coach_review_enabled"):
        checks.append(
            {
                "status": "注意",
                "item": "复盘模式",
                "message": "复盘模式关闭，触发词不会进入复盘",
            }
        )
    if switches.get("proactive_enabled"):
        checks.append(
            {
                "status": "注意",
                "item": "主动消息",
                "message": "主动消息已开启，请确认 reason gate 仍未接管或频率安全",
            }
        )
    if switches.get("state_machine_enabled"):
        checks.append(
            {
                "status": "注意",
                "item": "状态机",
                "message": "状态机已开启，请确认仍只控制表达分寸",
            }
        )

    total_size = int(memory.get("total_size_bytes") or 0)
    total_limit = int(memory.get("total_limit_bytes") or 0)
    if total_limit > 0 and total_size >= int(total_limit * 0.8):
        checks.append(
            {
                "status": "建议",
                "item": "容量",
                "message": "记忆数据接近容量上限，建议导出或清理",
            }
        )

    checks.append(
        {
            "status": "通过",
            "item": "群聊隔离",
            "message": "群聊不注入 owner 私聊记忆",
        }
    )
    checks.append(
        {
            "status": "通过",
            "item": "记忆管理页",
            "message": "记忆管理页可用",
        }
    )
    return checks


def build_console_overview_status(
    store: MemoryStore,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a masked read-only status payload for the Console page."""

    owner = _owner_selection(store, config)
    switches = {
        "yushu_private_enabled": _bool(config, "yushu_private_enabled", True),
        "group_light_mode": _bool(config, "group_light_mode", True),
        "yushu_group_enabled": _bool(config, "yushu_group_enabled", False),
        "prompt_injection_enabled": _bool(config, "prompt_injection_enabled", False),
        "memory_injection_enabled": _bool(config, "memory_injection_enabled", False),
        "coach_review_enabled": _bool(config, "coach_review_enabled", False),
        "state_machine_enabled": _bool(config, "state_machine_enabled", False),
        "proactive_enabled": _bool(config, "proactive_enabled", False),
        "debug_mode": _bool(config, "debug_mode", False),
    }
    memory = _memory_summary(store, config, owner["selected_owner_id"])
    return {
        "stage": "stage6b_console_overview",
        "plugin_version": PLUGIN_VERSION,
        "switches": switches,
        "owner": {
            "owner_count": owner["owner_count"],
            "selected_owner": owner["selected_owner"],
            "selected_owner_hint": owner["selected_owner_hint"],
            "owner_options": owner["owner_options"],
            "private_scope_enabled": switches["yushu_private_enabled"],
            "group_isolation": "群聊不注入 owner 私聊记忆",
        },
        "memory": memory,
        "coach_review_trigger_keywords": get_coach_review_trigger_keywords(config),
        "coach_review_exit_keywords": get_coach_review_exit_keywords(config),
        "type_help": memory_type_help_items(),
        "health_checks": _health_checks(switches, memory),
        "keyword_config_hint": "这些词可在 AstrBot 插件配置里修改",
        "links": {
            "memory_console": "#/plugin-page/yushu_core/memory-console",
        },
        "commands": get_help_commands(),
        "memory_type_short_help": memory_type_short_help(),
        "safety": {
            "group_bot_mode": "群聊只当普通 bot",
            "group_memory_isolation": "群聊不注入 owner 私聊记忆",
            "owner_group_skip": "owner 在群里发消息也不注入私聊 memory",
            "proactive_status": "proactive 当前未接管或 disabled",
        },
    }
