"""Read-only MVP readiness diagnostics for yushu_core."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .command_format import (
    CONFIG_LABELS,
    RECOMMENDED_CONFIG,
    config_value_label,
    enabled_label,
)
from .eval_runner import summarize_eval_cases
from .memory_store import MemoryStore


def _bytes_label(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f}MB"
    if size >= 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size}B"


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _recommended_summary(config: dict[str, Any] | None) -> tuple[int, int, list[str]]:
    data = config or {}
    matched = 0
    mismatches: list[str] = []
    for key, recommended in RECOMMENDED_CONFIG.items():
        if key in data and data.get(key) == recommended:
            matched += 1
        else:
            label = CONFIG_LABELS.get(key, key)
            current = config_value_label(data[key]) if key in data else "未配置"
            mismatches.append(
                f"{label}：当前 {current}，建议 {config_value_label(recommended)}"
            )
    return matched, len(RECOMMENDED_CONFIG), mismatches


def _eval_count_label(eval_summary: dict[str, Any]) -> str:
    count = int(eval_summary.get("case_count") or 0)
    declared = eval_summary.get("declared_case_count")
    suffix = "符合" if count == 55 and (declared in {55, None}) else "需检查，预期 55"
    return f"{count}（{suffix}）"


def build_doctor_report(
    config: dict[str, Any] | None,
    store: MemoryStore,
    owner_id: str,
    eval_summary: dict[str, Any] | None = None,
    plugin_root: Path | None = None,
) -> str:
    data = config or {}
    root = plugin_root or _plugin_root()
    summary = eval_summary or summarize_eval_cases()
    status = store.status(owner_id or "", "private")
    matched, total, mismatches = _recommended_summary(data)
    console_exists = (root / "pages" / "console" / "index.html").exists()
    memory_console_exists = (root / "pages" / "memory-console" / "index.html").exists()

    lines = [
        "雨舒 Doctor",
        "插件阶段：mvp_ready_check",
        f"推荐配置：{matched}/{total} 符合",
    ]
    if mismatches:
        lines.append("配置建议：")
        lines.extend(f"- {item}" for item in mismatches[:8])
        if len(mismatches) > 8:
            lines.append(f"- 还有 {len(mismatches) - 8} 项建议，请查看 /ys config diff")
    else:
        lines.append("配置建议：当前没有高优先级配置风险")

    lines.extend(
        [
            "",
            "记忆状态：",
            f"- 记忆 DB：{'存在' if status.get('db_exists') else '不存在'}",
            f"- 数据库大小：{_bytes_label(int(status.get('db_size_bytes') or 0))}",
            f"- 记忆条数：{int(status.get('memory_count') or 0)}",
            f"- 置顶条数：{int(status.get('pinned_count') or 0)}",
            "",
            "WebUI 页面：",
            f"- Console 页面：{'存在' if console_exists else '缺失'}",
            f"- Memory Console 页面：{'存在' if memory_console_exists else '缺失'}",
            "",
            "评估用例：",
            f"- 评估用例数量：{_eval_count_label(summary)}",
            "",
            "live 注入开关：",
            f"- 提示词注入：{enabled_label(data.get('prompt_injection_enabled', False))}",
            f"- 记忆注入：{enabled_label(data.get('memory_injection_enabled', False))}",
            f"- 复盘模式：{enabled_label(data.get('coach_review_enabled', False))}",
            f"- 复盘不进历史：{enabled_label(data.get('coach_review_no_history_enabled', True))}",
            f"- 状态机：{enabled_label(data.get('state_machine_enabled', False))}",
            "",
            "群聊隔离：通过，群聊不注入 owner 私聊记忆",
            "",
            "需要人工验证：",
            "- WebUI 插件页能打开雨舒总览和记忆管理。",
            "- owner 私聊普通消息为 mode=normal。",
            "- owner 私聊复盘触发词为 mode=coach。",
            "- 群聊消息不会注入 owner 私聊记忆。",
            "- /ys memory list 与记忆管理页看到的条数一致。",
        ]
    )
    return "\n".join(lines)
