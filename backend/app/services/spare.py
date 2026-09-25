"""器材领用业务规则：状态流转、字段校验、工区归属与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.identity import Operator
from app.store import store

MODULE = "spare"
REQUIRED_FIELDS = ["领用单号", "器材名称", "器材规格"]
STATUS_ORDER = ["待审批", "已批准", "已领用", "已退回"]
ACTION_RULES = {"批准领用": "已批准", "确认发放": "已领用", "退回器材": "已退回"}
NEGATIVE_ACTIONS = []


class SpareService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("领用单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(
        self,
        values: dict[str, Any],
        operator: Operator,
    ) -> tuple[dict[str, Any] | None, list[str], str | None]:
        """登记器材领用单：归属工区以账号为准，不能替别的工区登记。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, None
        requested = str(values.get("所属工区") or "").strip()
        if operator.known and operator.section and requested and requested != operator.section:
            return (
                None,
                [],
                f"器材领用单只能登记到本工区（{operator.section}），不能登记到{requested}，已拒绝",
            )
        with store.write_lock:
            rows = store.rows(MODULE)
            entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
            entry["所属工区"] = operator.section or requested
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            rows.append(entry)
        return entry, [], None

    def run_action(self, entry_id: int, action: str, operator: Operator) -> tuple[dict[str, Any] | None, str]:
        with store.write_lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"器材领用单 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于器材领用可执行范围"
            denial = self._section_denial(entry, operator)
            if denial is not None:
                return None, denial
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"
            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            return entry, f"器材领用单已{action}"

    def _section_denial(self, entry: dict[str, Any], operator: Operator) -> str | None:
        """器材记录按工区归属管理：跨工区账号只读可见，改动一律拒绝并说明原因。"""
        serial = entry.get("领用单号") or f"#{entry.get('id')}"
        if not operator.known:
            return f"账号 {operator.name} 未登记，仅有只读权限，不能改动器材领用单 {serial}"
        section = str(entry.get("所属工区") or "").strip()
        if section and operator.section != section:
            return (
                f"器材领用单 {serial}（更换器材记录）归属{section}，当前账号 {operator.name} 属于{operator.section}，跨工区不能改动，已拒绝"
            )
        return None
