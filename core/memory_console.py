"""Memory Console helpers for yushu_core.

This module builds masked view payloads for the WebUI page and exposes
single-item write wrappers that keep owner/scope checks server-side.
"""

from __future__ import annotations

import hashlib
import json
from html import escape
from typing import Any
from urllib.parse import urlencode

from .memory_store import ALLOWED_MEMORY_TYPES, MemoryStore, MemoryStoreError
from .memory_types import (
    memory_type_display,
    normalize_memory_type,
)


def type_display_label(memory_type: str | None, *, include_raw: bool = True) -> str:
    return memory_type_display(memory_type, include_raw=include_raw)


def memory_type_help_items() -> list[dict[str, str]]:
    from .memory_types import memory_type_help_items as _memory_type_help_items

    return _memory_type_help_items()


def _bytes_label(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f}MB"
    if size >= 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size}B"


def _owners(config: dict[str, Any] | None) -> list[str]:
    owners = (config or {}).get("owner_user_ids", [])
    if not isinstance(owners, list):
        return []
    return [str(item or "").strip() for item in owners if str(item or "").strip()]


def _owner_index(owner_key: str | None, owner_count: int) -> int:
    key = str(owner_key or "").strip().lower()
    if key.startswith("owner_"):
        key = key.removeprefix("owner_")
    try:
        index = int(key) - 1
    except ValueError:
        return 0
    if index < 0 or index >= owner_count:
        return 0
    return index


def _owner_kind(owner_id: str) -> str:
    return "session-like" if ":" in str(owner_id or "") else "bare-like"


def _private_memory_counts(store: MemoryStore, owner_ids: list[str]) -> list[int]:
    counts: list[int] = []
    for owner_id in owner_ids:
        try:
            counts.append(int(store.count_memories(owner_id, "private") or 0))
        except Exception:
            counts.append(0)
    return counts


def _default_owner_index(private_counts: list[int]) -> int:
    if not private_counts:
        return 0
    best_index = 0
    best_count = 0
    for index, count in enumerate(private_counts):
        if count > best_count:
            best_index = index
            best_count = count
    return best_index if best_count > 0 else 0


def _selected_owner_index(
    owner_key: str | None,
    owner_count: int,
    private_counts: list[int],
) -> int:
    if owner_count <= 0:
        return 0
    if str(owner_key or "").strip():
        return _owner_index(owner_key, owner_count)
    return _default_owner_index(private_counts)


def _owner_count_label(count: int) -> str:
    return f"{count}条私聊记忆"


def _owner_kind_label(kind: str) -> str:
    return "会话ID" if kind == "session-like" else "用户ID"


def _owner_label(index: int, kind: str, count: int) -> str:
    return f"Owner {index + 1}（{_owner_kind_label(kind)}，{_owner_count_label(count)}）"


def _owner_details(
    owner_labels: list[str],
    owner_ids: list[str],
    private_counts: list[int],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for index, label in enumerate(owner_labels):
        count = private_counts[index] if index < len(private_counts) else 0
        kind = _owner_kind(owner_ids[index] if index < len(owner_ids) else "")
        details.append(
            {
                "key": label,
                "label": _owner_label(index, kind, count),
                "kind": kind,
                "memory_count": count,
                "has_private_memories": count > 0,
            }
        )
    return details


def _selected_owner_hint(selected_owner_index: int, owner_id: str | None, count: int) -> str:
    kind = _owner_kind(owner_id or "")
    return f"当前选择：{_owner_label(selected_owner_index, kind, count)}"


def _confirm_delete(value: object) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "confirm", "confirmed"}


def _resolve_owner_scope(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None,
    scope_key: str | None,
) -> tuple[str, str]:
    owner_ids = _owners(config)
    if not owner_ids:
        raise MemoryStoreError("owner_not_configured")
    private_counts = _private_memory_counts(store, owner_ids)
    owner_index = _selected_owner_index(owner_key, len(owner_ids), private_counts)
    owner_id = owner_ids[owner_index]
    scope_options = _scope_options(store, owner_id)
    scope, _ = _resolve_scope(scope_key, scope_options)
    return owner_id, scope


def _scope_options(store: MemoryStore, user_id: str | None) -> list[dict[str, str]]:
    if not user_id:
        return [{"key": "private", "label": "private", "scope": "private"}]

    scopes = store.list_scopes(user_id)
    if "private" not in scopes:
        scopes.insert(0, "private")

    options: list[dict[str, str]] = []
    group_index = 1
    other_index = 1
    for scope in scopes:
        if scope == "private":
            options.append({"key": "private", "label": "private", "scope": scope})
        elif str(scope).startswith("group:"):
            key = f"group_rule_{group_index}"
            group_index += 1
            options.append({"key": key, "label": key, "scope": scope})
        else:
            key = f"scope_{other_index}"
            other_index += 1
            options.append({"key": key, "label": key, "scope": scope})
    return options


def _resolve_scope(
    scope_key: str | None,
    options: list[dict[str, str]],
) -> tuple[str, str]:
    requested = str(scope_key or "private").strip() or "private"
    for option in options:
        if option["key"] == requested:
            return option["scope"], option["key"]
    private = next((option for option in options if option["key"] == "private"), None)
    if private:
        return private["scope"], private["key"]
    first = options[0]
    return first["scope"], first["key"]


def _normalize_memory_type(memory_type: str | None) -> str | None:
    value = normalize_memory_type(memory_type)
    return value if value in ALLOWED_MEMORY_TYPES else None


def _normalize_pinned(value: str | bool | None) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "pinned"}:
        return True
    if text in {"0", "false", "no", "unpinned"}:
        return False
    return None


def _safe_item(item: dict[str, Any]) -> dict[str, Any]:
    memory_type = str(item.get("type") or "")
    return {
        "id": str(item.get("id") or ""),
        "type": memory_type,
        "type_label": type_display_label(memory_type),
        "pinned": int(item.get("pinned") or 0),
        "created_at": str(item.get("created_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
        "expires_at": str(item.get("expires_at") or "none"),
        "short_content": str(item.get("short_content") or ""),
    }


def _safe_detail(item: dict[str, Any], scope_key: str) -> dict[str, Any]:
    memory_type = str(item.get("type") or "")
    return {
        "id": str(item.get("id") or ""),
        "scope": scope_key,
        "type": memory_type,
        "type_label": type_display_label(memory_type),
        "content": str(item.get("content") or ""),
        "confidence": item.get("confidence"),
        "created_at": str(item.get("created_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
        "expires_at": str(item.get("expires_at") or "none"),
        "source": str(item.get("source") or ""),
        "pinned": int(item.get("pinned") or 0),
    }


def _console_status(store: MemoryStore, user_id: str | None, scope: str) -> dict[str, Any]:
    raw = store.status(user_id or "", scope)
    return {
        "db_size": _bytes_label(int(raw.get("db_size_bytes") or 0)),
        "exports_size": _bytes_label(int(raw.get("exports_size_bytes") or 0)),
        "total_size": _bytes_label(int(raw.get("total_size_bytes") or 0)),
        "memory_count": int(raw.get("memory_count") or 0),
        "pinned_count": int(raw.get("pinned_count") or 0),
        "db_limit": _bytes_label(int(raw.get("db_limit_bytes") or 0)),
        "exports_limit": _bytes_label(int(raw.get("exports_limit_bytes") or 0)),
        "total_limit": _bytes_label(int(raw.get("total_limit_bytes") or 0)),
    }


def build_memory_console_snapshot(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
    memory_type: str | None = None,
    pinned: str | bool | None = None,
    memory_id: str | None = None,
) -> dict[str, Any]:
    """Build a fully masked read-only Memory Console snapshot."""

    owner_ids = _owners(config)
    owner_labels = [f"owner_{idx + 1}" for idx in range(len(owner_ids))]
    private_counts = _private_memory_counts(store, owner_ids)
    selected_owner_index = _selected_owner_index(
        owner_key,
        len(owner_ids),
        private_counts,
    )
    selected_owner_id = owner_ids[selected_owner_index] if owner_ids else None
    selected_owner_key = (
        owner_labels[selected_owner_index] if owner_labels else "owner_none"
    )
    selected_private_count = (
        private_counts[selected_owner_index]
        if selected_owner_index < len(private_counts)
        else 0
    )

    scope_options = _scope_options(store, selected_owner_id)
    selected_scope, selected_scope_key = _resolve_scope(scope_key, scope_options)
    selected_type = _normalize_memory_type(memory_type)
    selected_pinned = _normalize_pinned(pinned)

    status = _console_status(store, selected_owner_id, selected_scope)
    items: list[dict[str, Any]] = []
    detail = None
    detail_error = None

    if selected_owner_id:
        rows = store.list_memories(selected_owner_id, selected_scope, selected_type)
        for row in rows:
            if selected_pinned is not None and bool(int(row.get("pinned") or 0)) is not selected_pinned:
                continue
            items.append(_safe_item(row))

        requested_memory_id = str(memory_id or "").strip()
        if requested_memory_id:
            try:
                raw_detail = store.get_memory(
                    selected_owner_id,
                    selected_scope,
                    requested_memory_id,
                )
                detail = _safe_detail(raw_detail, selected_scope_key)
            except MemoryStoreError:
                detail_error = "memory_not_found"

    return {
        "mode": "readonly",
        "owner_configured": bool(owner_ids),
        "owner_options": owner_labels,
        "owner_details": _owner_details(owner_labels, owner_ids, private_counts),
        "selected_owner": selected_owner_key,
        "selected_owner_hint": _selected_owner_hint(
            selected_owner_index,
            selected_owner_id,
            selected_private_count,
        ),
        "scope_options": [
            {"key": option["key"], "label": option["label"]}
            for option in scope_options
        ],
        "selected_scope": selected_scope_key,
        "selected_type": selected_type or "",
        "selected_pinned": (
            "true" if selected_pinned is True else "false" if selected_pinned is False else ""
        ),
        "status": status,
        "items": items,
        "detail": detail,
        "detail_error": detail_error,
        "allowed_types": sorted(ALLOWED_MEMORY_TYPES),
        "type_help": memory_type_help_items(),
    }


def delete_memory_console_item(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
    memory_id: str | None = None,
    confirm: object = None,
) -> dict[str, Any]:
    """Delete one memory for the selected masked owner/scope only."""

    if not _confirm_delete(confirm):
        raise MemoryStoreError("delete_confirm_required")
    requested_memory_id = str(memory_id or "").strip()
    if not requested_memory_id:
        raise MemoryStoreError("memory_not_found")

    owner_id, scope = _resolve_owner_scope(
        store,
        config,
        owner_key=owner_key,
        scope_key=scope_key,
    )
    store.delete_memory(owner_id, scope, requested_memory_id)
    return {"deleted": True, "memory_id": requested_memory_id}


def edit_memory_console_item(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
    memory_id: str | None = None,
    memory_type: str | None = None,
    content: str | None = None,
    confirm: object = None,
) -> dict[str, Any]:
    """Edit one memory for the selected masked owner/scope only."""

    if not _confirm_delete(confirm):
        raise MemoryStoreError("edit_confirm_required")
    requested_memory_id = str(memory_id or "").strip()
    if not requested_memory_id:
        raise MemoryStoreError("memory_not_found")

    owner_id, scope = _resolve_owner_scope(
        store,
        config,
        owner_key=owner_key,
        scope_key=scope_key,
    )
    updated = store.update_memory_fields(
        owner_id,
        scope,
        requested_memory_id,
        str(memory_type or ""),
        str(content or ""),
    )
    return {
        "updated": True,
        "memory_id": requested_memory_id,
        "type": str(updated.get("type") or ""),
    }


def pin_memory_console_item(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
    memory_id: str | None = None,
    pinned: bool,
) -> dict[str, Any]:
    """Pin or unpin one memory for the selected masked owner/scope only."""

    requested_memory_id = str(memory_id or "").strip()
    if not requested_memory_id:
        raise MemoryStoreError("memory_not_found")

    owner_id, scope = _resolve_owner_scope(
        store,
        config,
        owner_key=owner_key,
        scope_key=scope_key,
    )
    updated = store.set_pinned(owner_id, scope, requested_memory_id, bool(pinned))
    return {
        "updated": True,
        "memory_id": requested_memory_id,
        "pinned": bool(int(updated.get("pinned") or 0)),
    }


def _safe_export_path(path: object) -> str:
    name = str(path or "").replace("\\", "/").rsplit("/", 1)[-1]
    return f"exports/{name}" if name else "exports/unknown"


def export_memory_console_scope(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
    export_format: str | None = None,
) -> dict[str, Any]:
    """Export selected masked owner/scope memories without leaking paths."""

    owner_id, scope = _resolve_owner_scope(
        store,
        config,
        owner_key=owner_key,
        scope_key=scope_key,
    )
    result = store.export_memories(owner_id, scope, str(export_format or "md"))
    return {
        "format": str(result.get("format") or ""),
        "exported_count": int(result.get("exported_count") or 0),
        "skipped_sensitive_count": int(result.get("skipped_sensitive_count") or 0),
        "size": _bytes_label(int(result.get("size_bytes") or 0)),
        "size_bytes": int(result.get("size_bytes") or 0),
        "relative_path": _safe_export_path(result.get("path")),
    }


def _prune_token(owner_id: str, scope: str, plan: dict[str, Any]) -> str:
    memory_ids = plan.get("memory_ids")
    if not isinstance(memory_ids, list):
        memory_ids = []
    export_files = plan.get("export_files")
    if not isinstance(export_files, list):
        export_files = []
    payload = {
        "owner": owner_id,
        "scope": scope,
        "planned_memories": int(plan.get("planned_memories") or 0),
        "planned_export_files": int(plan.get("planned_export_files") or 0),
        "planned_bytes": int(plan.get("planned_bytes") or 0),
        "memory_ids": sorted(str(item or "") for item in memory_ids),
        "export_files": sorted(str(item or "") for item in export_files),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def _prune_plan_with_fingerprint(
    store: MemoryStore,
    user_id: str,
    scope: str,
) -> dict[str, Any]:
    result = store.prune(user_id, scope, confirm=False)
    memory_ids = []
    try:
        memory_ids = store._prunable_memory_ids(user_id, scope)
    except Exception:
        memory_ids = []
    export_files = []
    try:
        export_files = [
            f"{path.name}:{path.stat().st_size}"
            for path in store._old_export_files()
            if path.exists()
        ]
    except Exception:
        export_files = []
    result["memory_ids"] = memory_ids
    result["export_files"] = export_files
    return result


def _safe_prune_result(
    store: MemoryStore,
    user_id: str,
    scope: str,
    result: dict[str, Any],
    *,
    include_token: bool,
) -> dict[str, Any]:
    safe = {
        "planned_memories": int(result.get("planned_memories") or 0),
        "planned_export_files": int(result.get("planned_export_files") or 0),
        "planned_bytes": int(result.get("planned_bytes") or 0),
        "planned_size": _bytes_label(int(result.get("planned_bytes") or 0)),
        "deleted_memories": int(result.get("deleted_memories") or 0),
        "deleted_export_files": int(result.get("deleted_export_files") or 0),
        "status": _console_status(store, user_id, scope),
    }
    if include_token:
        safe["plan_token"] = _prune_token(user_id, scope, result)
    return safe


def prune_memory_console_dry_run(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
) -> dict[str, Any]:
    """Preview prune for selected masked owner/scope without deleting."""

    owner_id, scope = _resolve_owner_scope(
        store,
        config,
        owner_key=owner_key,
        scope_key=scope_key,
    )
    result = _prune_plan_with_fingerprint(store, owner_id, scope)
    return _safe_prune_result(store, owner_id, scope, result, include_token=True)


def prune_memory_console_confirm(
    store: MemoryStore,
    config: dict[str, Any] | None,
    *,
    owner_key: str | None = None,
    scope_key: str | None = None,
    plan_token: str | None = None,
) -> dict[str, Any]:
    """Confirm prune only when the supplied dry-run token matches."""

    token = str(plan_token or "").strip()
    if not token:
        raise MemoryStoreError("prune_dry_run_required")

    owner_id, scope = _resolve_owner_scope(
        store,
        config,
        owner_key=owner_key,
        scope_key=scope_key,
    )
    dry_run = _prune_plan_with_fingerprint(store, owner_id, scope)
    expected_token = _prune_token(owner_id, scope, dry_run)
    if token != expected_token:
        raise MemoryStoreError("prune_plan_mismatch")
    result = store.prune(owner_id, scope, confirm=True)
    return _safe_prune_result(store, owner_id, scope, result, include_token=False)


def _selected(value: str, current: str) -> str:
    return " selected" if value == current else ""


def _query(snapshot: dict[str, Any], **overrides: str) -> str:
    params = {
        "owner": snapshot.get("selected_owner") or "owner_1",
        "scope": snapshot.get("selected_scope") or "private",
    }
    if snapshot.get("selected_type"):
        params["type"] = str(snapshot["selected_type"])
    if snapshot.get("selected_pinned"):
        params["pinned"] = str(snapshot["selected_pinned"])
    params.update({key: value for key, value in overrides.items() if value})
    return urlencode(params)


def render_memory_console_html(snapshot: dict[str, Any]) -> str:
    """Render a small fallback page with only single-item action markers."""

    status = snapshot.get("status") or {}
    owner_options = snapshot.get("owner_options") or []
    owner_details = snapshot.get("owner_details") or []
    scope_options = snapshot.get("scope_options") or []
    allowed_types = snapshot.get("allowed_types") or []
    items = snapshot.get("items") or []
    detail = snapshot.get("detail")

    if owner_details:
        owner_select = "".join(
            f'<option value="{escape(str(owner.get("key") or ""))}"{_selected(str(owner.get("key") or ""), str(snapshot.get("selected_owner") or ""))}>{escape(str(owner.get("label") or owner.get("key") or ""))}</option>'
            for owner in owner_details
        )
    else:
        owner_select = "".join(
            f'<option value="{escape(owner)}"{_selected(owner, str(snapshot.get("selected_owner") or ""))}>{escape(owner)}</option>'
            for owner in owner_options
        )
    if not owner_select:
        owner_select = '<option value="owner_none" selected>owner_none</option>'
    owner_hint = escape(str(snapshot.get("selected_owner_hint") or ""))

    scope_select = "".join(
        f'<option value="{escape(option["key"])}"{_selected(option["key"], str(snapshot.get("selected_scope") or ""))}>{escape(option["label"])}</option>'
        for option in scope_options
    )

    type_select = '<option value="">全部</option>' + "".join(
        f'<option value="{escape(memory_type)}"{_selected(memory_type, str(snapshot.get("selected_type") or ""))}>{escape(type_display_label(memory_type))}</option>'
        for memory_type in allowed_types
    )
    pinned_select = "".join(
        [
            f'<option value=""{_selected("", str(snapshot.get("selected_pinned") or ""))}>全部</option>',
            f'<option value="true"{_selected("true", str(snapshot.get("selected_pinned") or ""))}>已置顶</option>',
            f'<option value="false"{_selected("false", str(snapshot.get("selected_pinned") or ""))}>未置顶</option>',
        ]
    )

    stat_names = {
        "db_size": "数据库大小",
        "exports_size": "导出文件大小",
        "total_size": "总占用",
        "memory_count": "记忆条数",
        "pinned_count": "置顶条数",
        "db_limit": "数据库上限",
        "exports_limit": "导出上限",
        "total_limit": "总上限",
    }
    stat_cards = "\n".join(
        f'<div class="stat"><span>{escape(label)}</span><strong>{escape(str(status.get(name, "")))}</strong></div>'
        for name, label in stat_names.items()
    )

    table_rows = []
    for item in items:
        href = "?" + _query(snapshot, memory_id=str(item.get("id") or ""))
        pinned_label = "已置顶" if int(item.get("pinned") or 0) == 1 else "未置顶"
        table_rows.append(
            "<tr>"
            f'<td><a href="{escape(href)}">{escape(str(item.get("id") or ""))}</a></td>'
            f'<td>{escape(str(item.get("type_label") or item.get("type") or ""))}</td>'
            f'<td>{escape(pinned_label)}</td>'
            f'<td>{escape(str(item.get("created_at") or ""))}</td>'
            f'<td>{escape(str(item.get("updated_at") or ""))}</td>'
            f'<td>{escape(str(item.get("expires_at") or ""))}</td>'
            f'<td>{escape(str(item.get("short_content") or ""))}</td>'
            "<td>"
            f'<button type="button" data-action="edit-memory" data-memory-id="{escape(str(item.get("id") or ""))}">编辑</button> '
            f'<button type="button" data-action="pin-memory" data-memory-id="{escape(str(item.get("id") or ""))}">置顶</button> '
            f'<button type="button" data-action="delete-memory" data-memory-id="{escape(str(item.get("id") or ""))}">删除</button>'
            "</td>"
            "</tr>"
        )
    table_body = "\n".join(table_rows) or (
        '<tr><td colspan="8" class="empty">暂无记忆</td></tr>'
    )

    detail_labels = {
        "id": "id",
        "scope": "范围",
        "type": "类型",
        "content": "内容",
        "confidence": "置信度",
        "created_at": "创建时间",
        "updated_at": "更新时间",
        "expires_at": "过期时间",
        "source": "来源",
        "pinned": "置顶状态",
    }
    if detail:
        detail_rows = "\n".join(
            f'<div class="detail-row"><span>{escape(detail_labels[key])}</span><strong>{escape(str((detail.get("type_label") if key == "type" else detail.get(key)) or ""))}</strong></div>'
            for key in [
                "id",
                "scope",
                "type",
                "content",
                "confidence",
                "created_at",
                "updated_at",
                "expires_at",
                "source",
                "pinned",
            ]
        )
    elif snapshot.get("detail_error"):
        detail_rows = (
            '<div class="detail-row"><span>详情</span><strong>memory_not_found</strong></div>'
        )
    else:
        detail_rows = (
            '<div class="detail-row"><span>详情</span><strong>请选择一条记忆</strong></div>'
        )

    type_help_rows = "\n".join(
        f'<div class="detail-row"><span>{escape(item["display"])}</span><strong>{escape(item["description"])}</strong></div>'
        for item in snapshot.get("type_help") or memory_type_help_items()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>记忆管理</title>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #202124; background: #f7f8fa; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    .subtle {{ color: #5f6368; margin: 0 0 20px; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 18px; }}
    .stat, .panel {{ background: #fff; border: 1px solid #dfe3e8; border-radius: 8px; padding: 12px; }}
    .stat span, .detail-row span {{ display: block; color: #5f6368; font-size: 12px; }}
    .stat strong {{ font-size: 18px; }}
    form {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: end; margin-bottom: 18px; }}
    label {{ display: grid; gap: 4px; color: #5f6368; font-size: 12px; }}
    select, button {{ height: 34px; border: 1px solid #cfd4dc; border-radius: 6px; background: #fff; padding: 0 10px; }}
    button {{ color: #1a73e8; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #dfe3e8; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 10px; border-bottom: 1px solid #edf0f2; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #f0f3f6; color: #3c4043; }}
    a {{ color: #1a73e8; text-decoration: none; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.8fr); gap: 16px; }}
    .detail-row {{ border-bottom: 1px solid #edf0f2; padding: 8px 0; }}
    .detail-row strong {{ word-break: break-word; }}
    .empty {{ color: #5f6368; text-align: center; }}
    @media (max-width: 860px) {{ .layout {{ grid-template-columns: 1fr; }} table {{ display: block; overflow-x: auto; }} }}
  </style>
</head>
<body>
<main data-mode="single-item-actions">
  <h1>记忆管理</h1>
  <p class="subtle">单条操作 only: 编辑、置顶/取消置顶、删除；不提供新增、全清或批量编辑入口。</p>
  <section class="stats">{stat_cards}</section>
  <p class="subtle">{owner_hint}</p>
  <section class="panel">
    <h2>类型说明</h2>
    {type_help_rows}
  </section>
  <form method="get">
    <label>当前 Owner<select name="owner">{owner_select}</select></label>
    <label>范围<select name="scope">{scope_select}</select></label>
    <label>类型<select name="type">{type_select}</select></label>
    <label>置顶状态<select name="pinned">{pinned_select}</select></label>
    <button type="submit">应用</button>
  </form>
  <section class="layout">
    <div>
      <table>
        <thead><tr><th>id</th><th>类型</th><th>置顶状态</th><th>创建时间</th><th>更新时间</th><th>过期时间</th><th>内容摘要</th><th>操作</th></tr></thead>
        <tbody>{table_body}</tbody>
      </table>
    </div>
    <aside class="panel">
      <h2>详情</h2>
      {detail_rows}
    </aside>
  </section>
</main>
</body>
</html>"""


def memory_console_hint() -> str:
    return "Memory Console: 在 AstrBot WebUI -> 插件管理 -> yushu_core -> memory-console 页面打开"
