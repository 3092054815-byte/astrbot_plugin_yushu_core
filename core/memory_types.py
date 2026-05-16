"""Shared yushu memory type labels and aliases."""

from __future__ import annotations


TYPE_LABELS = {
    "profile": "个人资料",
    "preference": "偏好",
    "boundary": "边界",
    "open_thread": "未完话题",
    "skill_goal": "练习目标",
    "relationship": "关系线索",
    "fact": "事实",
    "group_rule": "群规",
}

TYPE_DESCRIPTIONS = {
    "profile": "稳定身份/背景摘要。",
    "preference": "你喜欢的回复风格或互动偏好。",
    "boundary": "不希望被怎样对待，或需要避开的表达。",
    "open_thread": "下次可接上的开放话题。",
    "skill_goal": "沟通表达、边界、邀约、降焦虑等训练目标。",
    "relationship": "现实关系中的阶段、氛围、注意点。",
    "fact": "普通事实信息，避免敏感隐私。",
    "group_rule": "群聊层面的公开规则，不用于 owner 私聊亲密记忆。",
}

TYPE_ALIASES = {
    "profile": {"profile", "个人资料", "资料", "个人信息"},
    "preference": {"preference", "偏好", "喜好", "回复偏好"},
    "boundary": {"boundary", "边界", "底线", "禁忌"},
    "open_thread": {"open_thread", "未完话题", "开放话题", "待续话题"},
    "skill_goal": {"skill_goal", "练习目标", "训练目标", "技能目标"},
    "relationship": {"relationship", "关系线索", "关系", "关系状态"},
    "fact": {"fact", "事实", "信息", "普通事实"},
    "group_rule": {"group_rule", "群规", "群规则", "群聊规则"},
}

TYPE_ORDER = [
    "profile",
    "preference",
    "boundary",
    "open_thread",
    "skill_goal",
    "relationship",
    "fact",
    "group_rule",
]

_ALIAS_TO_CANONICAL = {
    alias.strip().lower(): canonical
    for canonical, aliases in TYPE_ALIASES.items()
    for alias in aliases
}


def normalize_memory_type(input_type: str | None) -> str | None:
    value = str(input_type or "").strip()
    if not value:
        return None
    return _ALIAS_TO_CANONICAL.get(value.lower())


def memory_type_display(memory_type: str | None, *, include_raw: bool = True) -> str:
    raw = str(memory_type or "").strip()
    label = TYPE_LABELS.get(raw)
    if not label:
        return raw
    return f"{label}（{raw}）" if include_raw else label


def memory_type_help_items() -> list[dict[str, str]]:
    return [
        {
            "type": memory_type,
            "label": TYPE_LABELS[memory_type],
            "display": memory_type_display(memory_type),
            "description": TYPE_DESCRIPTIONS[memory_type],
        }
        for memory_type in TYPE_ORDER
    ]


def memory_type_help_text() -> str:
    lines = ["记忆类型无效。", "可用类型："]
    for memory_type in TYPE_ORDER:
        lines.append(f"- {memory_type_display(memory_type)}")
    return "\n".join(lines)


def memory_type_inline_help() -> str:
    return (
        "类型可用中文或英文，例如 偏好/preference。"
        "可用类型：profile/个人资料，preference/偏好，boundary/边界，"
        "open_thread/未完话题，skill_goal/练习目标，relationship/关系线索，"
        "fact/事实，group_rule/群规。"
    )
