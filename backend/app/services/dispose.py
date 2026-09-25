"""故障处置业务规则：状态流转、字段校验、归属约束与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.identity import ROLE_ACCEPTOR, Operator
from app.store import store

MODULE = "dispose"
REQUIRED_FIELDS = ["处置单号", "关联故障", "处置措施"]
STATUS_ORDER = ["待受理", "处置中", "待验收", "已验收"]
ACTION_RULES = {"受理处置": "处置中", "提交验收": "待验收", "确认验收": "已验收"}
NEGATIVE_ACTIONS = []
ACCEPT_ACTION = "确认验收"
UNIQUE_KEY = "处置单号"


class DisposeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # 读取时再按处置单号兜一道去重，防止历史脏数据在列表与详情里重复、错位
        rows = store.dedupe(store.rows(MODULE), UNIQUE_KEY)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get(UNIQUE_KEY, ""))]
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
        """登记处置单。返回（记录、缺失字段、说明）：同号单据重复提交只返回原单。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, None
        serial = str(values.get(UNIQUE_KEY) or "").strip()
        with store.write_lock:
            rows = store.rows(MODULE)
            for row in rows:
                if str(row.get(UNIQUE_KEY) or "").strip() == serial:
                    # 同一张单重复登记（含连点、超时重试）直接返回原记录，不再生成第二行
                    return row, [], f"处置单 {serial} 已存在，重复提交已忽略，返回原记录"
            entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
            # 归属工区以提交账号为准，不允许替别的工区登记处置单
            entry["所属工区"] = operator.section or str(values.get("所属工区") or "").strip()
            entry["更换器材"] = str(values.get("更换器材") or "").strip()
            entry["处置人员"] = str(values.get("处置人员") or "").strip()
            entry["完成时间"] = str(values.get("完成时间") or "").strip()
            entry["验收人员"] = str(values.get("验收人员") or "").strip()
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            rows.append(entry)
        return entry, [], None

    def run_action(self, entry_id: int, action: str, operator: Operator) -> tuple[dict[str, Any] | None, str]:
        with store.write_lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"处置单 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于故障处置可执行范围"
            if action == ACCEPT_ACTION:
                return self._confirm_accept(entry, operator)
            # 受理处置、提交验收沿用原有流转口径，不加新的归属限制
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"
            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            return entry, f"处置单已{action}"

    def _confirm_accept(
        self, entry: dict[str, Any], operator: Operator
    ) -> tuple[dict[str, Any] | None, str]:
        """确认验收：只有本工区的验收人员能提交；已验收的单重复提交不再改动结果。"""
        serial = entry.get(UNIQUE_KEY) or f"#{entry.get('id')}"
        if not operator.known:
            return None, f"账号 {operator.name} 未登记，仅有只读权限，不能确认验收"
        if operator.role != ROLE_ACCEPTOR:
            return (
                None,
                f"处置单 {serial} 只能由验收人员确认验收，当前账号 {operator.name} 的角色是{operator.role}，已拒绝",
            )
        section = str(entry.get("所属工区") or "").strip()
        if section and operator.section != section:
            return (
                None,
                f"处置单 {serial} 归属{section}，当前账号 {operator.name} 属于{operator.section}，跨工区不能确认验收，已拒绝",
            )
        if entry.get("status") == STATUS_ORDER[-1]:
            # 幂等：并发或重复提交只能得到同一条验收结果，不覆盖前一位验收人员与处置措施
            return entry, f"处置单 {serial} 已由{entry.get('验收人员') or '验收人员'}完成验收，重复提交未改动验收结果"
        if entry.get("status") != "待验收":
            return None, f"处置单 {serial} 当前为{entry.get('status')}，需先提交验收、进入待验收后才能确认"
        target = ACTION_RULES[ACCEPT_ACTION]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = False
        entry["验收人员"] = operator.name
        entry["验收时间"] = date.today().isoformat()
        return entry, f"处置单 {serial} 已由{operator.name}确认验收"
