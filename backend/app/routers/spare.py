"""器材领用接口：维护器材领用单，覆盖批准领用、确认发放、退回器材等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.identity import OPERATOR_HEADER, resolve_operator
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.spare import SpareService

router = APIRouter(prefix="/api/spare", tags=["器材领用"])

service = SpareService()

LIST_FIELDS = ["领用单号", "器材名称", "器材规格", "领用数量", "领用人员", "领用日期", "所属工区", "领用状态"]
STATUSES = ["待审批", "已批准", "已领用", "已退回"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按领用单号检索"),
    status: str | None = Query(default=None, description="待审批、已批准、已领用、已退回"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按领用单号与状态过滤器材领用列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条器材领用单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"器材领用单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(
    payload: EntryPayload,
    x_operator: str | None = Header(default=None, alias=OPERATOR_HEADER),
) -> ActionResult:
    """登记一条器材领用单，缺字段或跨工区登记时说明原因而不是静默丢弃。"""
    operator = resolve_operator(x_operator)
    entry, missing, note = service.create_entry(payload.values, operator)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry is None:
        return ActionResult(ok=False, message=note or "器材领用单登记被拒绝")
    return ActionResult(ok=True, message=note or "器材领用单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_operator: str | None = Header(default=None, alias=OPERATOR_HEADER),
) -> ActionResult:
    """对单条器材领用单执行批准领用、确认发放、退回器材；跨工区改动会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    operator = resolve_operator(x_operator)
    entry, message = service.run_action(entry_id, action, operator)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出器材领用清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "spare", "total": total, "items": items}
