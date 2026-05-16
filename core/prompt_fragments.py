"""Prompt fragment builders for Stage 5A preview only."""

from __future__ import annotations

from typing import Any

from .yushu_state import normalize_state


def _format_memory_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "- 无"
    return "\n".join(
        f"- {item.get('type')}：{item.get('content')}" for item in items
    )


def build_owner_private_fragment(
    items: list[dict[str, Any]],
    state: dict[str, Any] | None,
) -> str:
    normalized = normalize_state(state)
    return "\n".join(
        [
            "[YUSHU_OWNER_PRIVATE_CONTEXT]",
            "作用域：owner 私聊",
            "模式：角色内",
            "记忆策略：",
            "- 只使用下方短摘要。",
            "- 不要提 memory id。",
            "- 不要提数据库。",
            "- 不要声称记住了摘要之外的内容。",
            "- 不要把历史复盘内容当作长期记忆；长期依据只来自短记忆摘要。",
            "- 尊重边界，保留用户自主。",
            "",
            "短记忆：",
            _format_memory_lines(items),
            "",
            "状态提示：",
            f"关系温度={normalized['relationship_warmth']}",
            f"边界压力={normalized['boundary_pressure']}",
            f"信任={normalized['trust']}",
            f"轻松度={normalized['playfulness']}",
            f"用户自主={normalized['user_autonomy']}",
            f"现实转化={normalized['real_world_transfer']}",
            f"练习焦点={normalized['practice_focus']}",
            "[/YUSHU_OWNER_PRIVATE_CONTEXT]",
        ]
    )


def build_coach_review_fragment(
    items: list[dict[str, Any]],
    state: dict[str, Any] | None,
) -> str:
    normalized = normalize_state(state)
    return "\n".join(
        [
            "[YUSHU_COACH_REVIEW_CONTEXT]",
            "作用域：owner 私聊",
            "模式：复盘",
            "说明：",
            "- 以沟通教练视角检查这次请求。",
            "- 回答要具体、实用、不过度评判。",
            "- 只在有帮助时才给改写版本。",
            "- 需要时附一个很小的现实练习步骤。",
            "- 复盘模式默认不调用工具，只做沟通建议。",
            "- 不自动保存任何内容。",
            "- 本轮复盘后回到角色内，除非用户继续要求复盘。",
            "- 本轮复盘内容只作为当轮建议，不作为长期事实、偏好或关系状态。只有手动保存到记忆的内容才可作为长期依据。",
            "",
            "可用短记忆：",
            _format_memory_lines(items),
            "",
            "状态提示：",
            f"边界压力={normalized['boundary_pressure']}",
            f"用户自主={normalized['user_autonomy']}",
            f"现实转化={normalized['real_world_transfer']}",
            "练习焦点=coach_review",
            "[/YUSHU_COACH_REVIEW_CONTEXT]",
        ]
    )


def build_group_light_fragment() -> str:
    return "\n".join(
        [
            "[YUSHU_GROUP_LIGHT_CONTEXT]",
            "作用域：群聊",
            "模式：群聊轻量",
            "说明：",
            "- 不使用 owner 私聊记忆。",
            "- 不暴露私聊关系上下文。",
            "- 群聊建议保持短、公开、适合所有人看到。",
            "- 如果有人要求复盘，只给简短公开建议。",
            "- 不改变 SpectreCore 群聊行为。",
            "[/YUSHU_GROUP_LIGHT_CONTEXT]",
        ]
    )


def build_proactive_fragment_design_only() -> str:
    return "\n".join(
        [
            "[YUSHU_PROACTIVE_DESIGN_CONTEXT]",
            "作用域：owner 私聊",
            "模式：仅保留设计说明",
            "说明：",
            "- 这段只保留未来主动策略设计说明。",
            "- Stage 5 不调用 proactive_chat。",
            "- Stage 5 不调度或发送主动消息。",
            "- proactive_desire 只可影响用户主动发言时的措辞。",
            "[/YUSHU_PROACTIVE_DESIGN_CONTEXT]",
        ]
    )
