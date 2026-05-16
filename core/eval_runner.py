"""Read-only eval case summary helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


EVAL_CASES_PATH = Path(
    "/root/astrbot/data/patch_work/yushu_design/eval_cases_v1_55.yaml"
)
CONTAINER_EVAL_CASES_PATH = Path(
    "/AstrBot/data/patch_work/yushu_design/eval_cases_v1_55.yaml"
)


def _resolve_eval_path(path: Path | str) -> Path:
    eval_path = Path(path)
    if eval_path.exists():
        return eval_path
    if eval_path == EVAL_CASES_PATH and CONTAINER_EVAL_CASES_PATH.exists():
        return CONTAINER_EVAL_CASES_PATH
    return eval_path


def _summary_with_pyyaml(path: Path) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore
    except Exception:
        return None

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = data.get("cases") or []
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    return {
        "exists": True,
        "case_count": len(cases),
        "declared_case_count": data.get("case_count"),
        "first_id": ids[0] if ids else "",
        "last_id": ids[-1] if ids else "",
    }


def summarize_eval_cases(path: Path | str = EVAL_CASES_PATH) -> dict[str, Any]:
    """Return case count and id range without calling any model."""

    eval_path = _resolve_eval_path(path)
    if not eval_path.exists():
        return {
            "exists": False,
            "case_count": 0,
            "declared_case_count": None,
            "first_id": "",
            "last_id": "",
        }

    summary = _summary_with_pyyaml(eval_path)
    if summary is not None:
        return summary

    text = eval_path.read_text(encoding="utf-8")
    declared_match = re.search(r"(?m)^case_count:\s*(\d+)\s*$", text)
    ids = re.findall(r"(?m)^\s*-\s*id:\s*([A-Za-z0-9_.:-]+)\s*$", text)
    return {
        "exists": True,
        "case_count": len(ids),
        "declared_case_count": int(declared_match.group(1))
        if declared_match
        else None,
        "first_id": ids[0] if ids else "",
        "last_id": ids[-1] if ids else "",
    }
