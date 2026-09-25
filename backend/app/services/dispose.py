"""故障处置业务规则：状态流转、归属校验与筛选口径都收在这里。"""
from __future__ import annotations

import threading
from typing import Any

from app.store import store

MODULE = "dispose"
REQUIRED_FIELDS = ["处置单号", "关联故障", "处置措施"]
OPTIONAL_FIELDS = ["更换器材", "处置人员", "完成时间", "验收人员", "所属工区"]
STATUS_ORDER = ["待受理", "处置中", "待验收", "已验收"]
ACTION_RULES = {"受理处置": "处置中", "提交验收": "待验收", "确认验收": "已验收"}
NEGATIVE_ACTIONS: list[str] = []

# 验收类动作的前置状态：不满足就直接拒绝，重复提交才不会覆盖已填写的内容
ACTION_SOURCE = {"提交验收": "处置中", "确认验收": "待验收"}
# 提交验收时允许随单更新的处置字段
SUBMIT_FIELDS = ["处置措施", "更换器材", "处置人员", "完成时间"]

# 内存库没有行级锁，登记与验收类动作都走这把锁，同一张处置单同时提交只落一条结果
_lock = threading.Lock()


class DisposeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        with _lock:
            self._purge_duplicates()
            rows = store.rows(MODULE)
            for row in rows:
                self._sync_display(row)
            if keyword:
                rows = [row for row in rows if keyword in str(row.get("处置单号", ""))]
            if status:
                rows = [row for row in rows if row.get("status") == status]
            total = len(rows)
            start = max(page - 1, 0) * size
            return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        with _lock:
            self._purge_duplicates()
            entry = store.find(MODULE, entry_id)
            if entry is not None:
                self._sync_display(entry)
            return entry

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        code = str(values.get("处置单号") or "").strip()
        with _lock:
            self._purge_duplicates()
            rows = store.rows(MODULE)
            if any(str(row.get("处置单号") or "").strip() == code for row in rows):
                return None, [f"处置单号 {code} 已存在，重复登记只保留最早一条"]
            entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
            entry.update({
                field: values.get(field)
                for field in OPTIONAL_FIELDS
                if str(values.get(field) or "").strip()
            })
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            self._sync_display(entry)
            rows.append(entry)
            return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        operator = str(values.get("操作人") or "").strip()
        section = str(values.get("操作工区") or "").strip()
        with _lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"处置单 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于故障处置可执行范围"
            source = ACTION_SOURCE.get(action)
            if source is not None and entry.get("status") != source:
                return None, self._source_message(action, entry)
            if action == "提交验收":
                denial = self._check_submit_scope(entry, section)
                if denial:
                    return None, denial
                self._apply_submit_fields(entry, values)
            elif action == "确认验收":
                denial = self._check_acceptance_scope(entry, operator, section)
                if denial:
                    return None, denial
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"
            entry["status"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            self._sync_display(entry)
            return entry, f"处置单已{action}"

    @staticmethod
    def _sync_display(row: dict[str, Any]) -> None:
        # 列表与详情里的「处置状态」列以状态机为准，避免显示与真实进度错位
        row["处置状态"] = str(row.get("status") or "")

    @staticmethod
    def _purge_duplicates() -> None:
        # 同一处置单号只保留最早登记的一条，清理历史遗留的重复行
        rows = store.rows(MODULE)
        seen: set[str] = set()
        kept: list[dict[str, Any]] = []
        for row in rows:
            code = str(row.get("处置单号") or "").strip()
            if code and code in seen:
                continue
            if code:
                seen.add(code)
            kept.append(row)
        if len(kept) != len(rows):
            rows[:] = kept

    @staticmethod
    def _source_message(action: str, entry: dict[str, Any]) -> str:
        status = str(entry.get("status") or "未知")
        if action == "提交验收":
            if status == "待验收":
                return "处置单已提交验收，重复提交不会覆盖已填写的处置措施"
            if status == "已验收":
                return "处置单已完成验收，无需再次提交"
            return "处置单尚未受理，请先受理处置再提交验收"
        return f"处置单当前状态为「{status}」，确认验收只在「待验收」状态可执行"

    @staticmethod
    def _check_submit_scope(entry: dict[str, Any], section: str) -> str | None:
        home = str(entry.get("所属工区") or "").strip()
        if home and section != home:
            return (
                f"处置单归属「{home}」，当前账号所属工区为「{section or '未设置'}」，"
                "不能改动他工区的处置内容与更换器材"
            )
        return None

    @staticmethod
    def _check_acceptance_scope(entry: dict[str, Any], operator: str, section: str) -> str | None:
        if not operator:
            return "确认验收需要当前账号信息，请先选择值班账号"
        owner = str(entry.get("验收人员") or "").strip()
        if not owner:
            return "该处置单未指定验收人员，不能确认验收"
        if operator != owner:
            return f"该处置单验收人员为「{owner}」，当前账号「{operator}」不是验收人员，确认验收已拒绝"
        home = str(entry.get("所属工区") or "").strip()
        if not home:
            return "该处置单未登记所属工区，不能确认验收"
        if section != home:
            return (
                f"处置单归属「{home}」，当前账号所属工区为「{section or '未设置'}」，"
                "跨工区不能确认验收"
            )
        return None

    @staticmethod
    def _apply_submit_fields(entry: dict[str, Any], values: dict[str, Any]) -> None:
        for field in SUBMIT_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = values[field]
