"""Chinese command output formatting for yushu_core."""

from __future__ import annotations

from typing import Any

from .memory_types import TYPE_LABELS, TYPE_ORDER, memory_type_display


def enabled_label(value: Any) -> str:
    return "已开启" if bool(value) else "已关闭"


def memory_mode_label(value: Any) -> str:
    labels = {
        "suggest": "建议保存",
        "manual": "手动保存",
        "off": "已关闭",
        "auto": "自动保存",
    }
    return labels.get(str(value or "suggest"), str(value or "suggest"))


def config_value_label(value: Any) -> str:
    if value is _UNCONFIGURED:
        return "未配置"
    if isinstance(value, bool):
        return enabled_label(value)
    text = str(value or "")
    if text in {"suggest", "manual", "off", "auto"}:
        return memory_mode_label(text)
    return text or "未配置"


def none_label(value: Any) -> str:
    text = str(value or "").strip()
    return text if text and text.lower() != "none" else "无"


def pinned_label(value: Any) -> str:
    try:
        return "是" if int(value or 0) == 1 else "否"
    except (TypeError, ValueError):
        return "否"


def scope_label(value: Any) -> str:
    text = str(value or "").strip()
    if text == "private":
        return "私聊"
    if text.startswith("group:") or text.startswith("group_"):
        return "群聊"
    return text or "无"


def source_label(value: Any) -> str:
    labels = {
        "manual": "手动",
        "auto": "自动",
        "suggest": "建议",
    }
    text = str(value or "").strip()
    return labels.get(text, text or "无")


def format_memory_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return "记忆为空"
    blocks = ["雨舒记忆列表"]
    for item in items:
        blocks.append(
            "\n".join(
                [
                    f"ID：{item.get('id')}",
                    f"类型：{memory_type_display(str(item.get('type') or ''))}",
                    f"置顶：{pinned_label(item.get('pinned'))}",
                    f"创建时间：{item.get('created_at')}",
                    f"内容摘要：{item.get('short_content')}",
                ]
            )
        )
    return "\n\n".join(blocks)


def format_memory_view(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            "雨舒记忆详情",
            f"ID：{item.get('id')}",
            f"范围：{scope_label(item.get('scope'))}",
            f"类型：{memory_type_display(str(item.get('type') or ''))}",
            f"内容：{item.get('content')}",
            f"置信度：{item.get('confidence')}",
            f"创建时间：{item.get('created_at')}",
            f"更新时间：{item.get('updated_at')}",
            f"过期时间：{none_label(item.get('expires_at'))}",
            f"来源：{source_label(item.get('source'))}",
            f"置顶：{pinned_label(item.get('pinned'))}",
        ]
    )


def format_memory_command_status(key: str, detail: Any | None = None) -> str:
    text = str(detail or "").strip()
    with_id = {
        "memory_added": "已新增记忆",
        "memory_edited": "已更新记忆",
        "memory_pinned": "已置顶",
        "memory_unpinned": "已取消置顶",
        "memory_cleared_private": "已清空私聊记忆",
    }
    fixed = {
        "memory_empty": "记忆为空",
        "memory_not_found": "未找到这条记忆",
        "memory_deleted": "已删除记忆",
        "memory_updated": "已更新记忆",
        "memory_off": "记忆功能已关闭",
        "memory_on": "记忆功能已开启",
        "memory_disabled": "记忆功能已禁用",
        "memory_exported": "记忆已导出",
        "manual_add_disabled": "手动新增记忆已禁用",
        "group_memory_requires_group_rule": "群聊只能新增群规类型记忆",
        "group_rule_disabled": "群规记忆已禁用",
        "export_disabled": "记忆导出已禁用",
        "invalid_memory_type": "记忆类型无效",
        "invalid_duration": "暂停时长无效",
        "sensitive_content": "内容包含敏感信息，已拒绝",
    }
    if key.startswith("memory_paused_until:"):
        return "记忆功能已暂停到：" + key.split(":", 1)[1].strip()
    if key in with_id:
        return f"{with_id[key]}：{text}" if text else with_id[key]
    return fixed.get(key, key)


def format_memory_export(result: dict[str, Any], size_label: str) -> str:
    return "\n".join(
        [
            format_memory_command_status("memory_exported"),
            f"格式：{result.get('format')}",
            f"导出条数：{result.get('exported_count')}",
            f"跳过敏感条数：{result.get('skipped_sensitive_count')}",
            f"大小：{size_label}",
            f"路径：{result.get('path')}",
        ]
    )


def format_memory_prune(mode: str, result: dict[str, Any], planned_bytes_label: str) -> str:
    title = "记忆清理预览" if mode == "dry-run" else "记忆清理结果"
    return "\n".join(
        [
            title,
            f"计划清理记忆：{result.get('planned_memories')}",
            f"已删除记忆：{result.get('deleted_memories')}",
            f"计划清理导出文件：{result.get('planned_export_files')}",
            f"已删除导出文件：{result.get('deleted_export_files')}",
            f"计划释放空间：{planned_bytes_label}",
        ]
    )


def config_audit_report(config: dict[str, Any] | None) -> str:
    data = config or {}
    checks = [
        ("提示词注入", bool(data.get("prompt_injection_enabled", False))),
        ("记忆注入", bool(data.get("memory_injection_enabled", False))),
        ("复盘模式", bool(data.get("coach_review_enabled", True))),
        ("调试模式", bool(data.get("debug_mode", False))),
        ("主动消息", bool(data.get("proactive_enabled", False))),
        ("群聊雨舒能力", bool(data.get("yushu_group_enabled", False))),
        ("状态机", bool(data.get("state_machine_enabled", False))),
    ]
    lines = ["雨舒配置检查"]
    for label, value in checks:
        lines.append(f"- {label}：{enabled_label(value)}")
    lines.append(f"- 记忆模式：{memory_mode_label(data.get('memory_mode', 'suggest'))}")

    suggestions: list[str] = []
    if data.get("debug_mode", False):
        suggestions.append("建议正式使用前关闭调试模式。")
    if not data.get("prompt_injection_enabled", False):
        suggestions.append("真实聊天不会注入雨舒上下文。")
    if not data.get("memory_injection_enabled", False):
        suggestions.append("记忆不会进入真实聊天。")
    if data.get("proactive_enabled", False):
        suggestions.append("主动消息仍需确认 reason gate。")
    if data.get("yushu_group_enabled", False):
        suggestions.append("群聊能力已开启，请确认隔离。")

    lines.append("")
    lines.append("建议项：")
    if suggestions:
        lines.extend(f"- {item}" for item in suggestions)
    else:
        lines.append("- 当前没有高优先级配置风险")
    return "\n".join(lines)


class _Unconfigured:
    pass


_UNCONFIGURED = _Unconfigured()


RECOMMENDED_CONFIG: dict[str, Any] = {
    "yushu_private_enabled": True,
    "group_light_mode": True,
    "yushu_group_enabled": False,
    "prompt_injection_enabled": True,
    "memory_injection_enabled": True,
    "coach_review_enabled": True,
    "state_machine_enabled": False,
    "proactive_enabled": False,
    "debug_mode": False,
    "proactive_chat_integration_enabled": False,
    "spectrecore_integration_enabled": False,
    "memory_private_only": True,
    "coach_review_owner_only": True,
    "proactive_private_only": True,
}


CONFIG_LABELS = {
    "yushu_private_enabled": "私聊雨舒",
    "group_light_mode": "群聊轻量模式",
    "yushu_group_enabled": "群聊雨舒能力",
    "prompt_injection_enabled": "提示词注入",
    "memory_injection_enabled": "记忆注入",
    "coach_review_enabled": "复盘模式",
    "state_machine_enabled": "状态机",
    "proactive_enabled": "主动消息",
    "debug_mode": "调试模式",
    "proactive_chat_integration_enabled": "proactive_chat 接入",
    "spectrecore_integration_enabled": "SpectreCore 接入",
    "memory_private_only": "记忆仅私聊",
    "coach_review_owner_only": "复盘仅 Owner",
    "proactive_private_only": "主动消息仅私聊",
}


CONFIG_REASONS = {
    "prompt_injection_enabled": "不开启时真实聊天不会注入雨舒上下文。",
    "memory_injection_enabled": "不开启时记忆不会进入真实聊天。",
    "debug_mode": "正式使用前减少日志。",
    "proactive_enabled": "reason gate 尚未接管前不建议主动发。",
    "yushu_group_enabled": "群聊只作为普通 bot，避免进入私聊陪练能力。",
    "proactive_chat_integration_enabled": "当前不接 proactive_chat，避免扩大作用域。",
    "spectrecore_integration_enabled": "当前不接 SpectreCore，避免扩大作用域。",
    "memory_private_only": "避免 owner 私聊记忆进入群聊或其他 scope。",
    "coach_review_owner_only": "复盘模式只允许 owner 私聊触发。",
    "proactive_private_only": "主动消息如未来开启也应限制私聊。",
}


def config_diff_report(config: dict[str, Any] | None) -> str:
    data = dict(config or {})
    changed: list[tuple[str, Any, Any, str]] = []
    unchanged: list[tuple[str, Any]] = []

    for key, recommended in RECOMMENDED_CONFIG.items():
        current = data[key] if key in data else _UNCONFIGURED
        if current is _UNCONFIGURED or current != recommended:
            changed.append((key, current, recommended, CONFIG_REASONS.get(key, "建议与当前安全运行设计保持一致。")))
        else:
            unchanged.append((key, current))

    lines = ["雨舒配置建议 diff"]
    lines.append("需要调整：")
    if changed:
        for key, current, recommended, reason in changed:
            label = CONFIG_LABELS.get(key, key)
            lines.append(
                f"- {label}：当前 {config_value_label(current)} -> 建议 {config_value_label(recommended)}"
            )
            lines.append(f"  原因：{reason}")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("无需调整：")
    if unchanged:
        for key, current in unchanged:
            lines.append(f"- {CONFIG_LABELS.get(key, key)}：{config_value_label(current)}")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("这里只读展示建议，不会自动修改配置。请在 AstrBot WebUI 插件配置里手动调整。")
    return "\n".join(lines)


def get_help_commands() -> list[dict[str, str]]:
    return [
        {"command": "/ys status", "description": "查看雨舒 Core 基础状态。"},
        {"command": "/ys doctor", "description": "运行 MVP 只读诊断。"},
        {"command": "/ys config audit", "description": "查看当前配置风险提示。"},
        {"command": "/ys config diff", "description": "查看当前值到推荐值的配置差异。"},
        {"command": "/ys injection status", "description": "查看提示词注入、记忆注入和复盘模式开关。"},
        {"command": "/ys memory status", "description": "查看记忆功能状态和容量限制。"},
        {"command": "/ys memory list", "description": "查看当前 owner 私聊记忆列表。"},
        {"command": "/ys memory add 偏好 <内容>", "description": "手动新增一条偏好记忆。"},
        {"command": "/ys memory export md", "description": "导出当前记忆为 Markdown。"},
        {"command": "/ys memory prune dry-run", "description": "预览可清理项目，不会真的删除。"},
    ]


def memory_type_short_help() -> str:
    labels = "、".join(TYPE_LABELS[memory_type] for memory_type in TYPE_ORDER)
    return f"记忆类型：{labels}。"


def format_yushu_help() -> str:
    lines = ["雨舒命令帮助"]
    lines.extend(
        f"{item['command']}：{item['description']}"
        for item in get_help_commands()
    )
    lines.append("记忆类型可用中文或英文：" + memory_type_short_help().removeprefix("记忆类型："))
    return "\n".join(lines)
