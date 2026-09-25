"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

import threading
from typing import Any

from app.seed import SEED_ROWS

# 各模块的业务唯一键：重启时按它清理历史重复数据，避免同一张单出现两行、明细错位
UNIQUE_KEYS: dict[str, str] = {
    "dispose": "处置单号",
}


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        # 写动作的临界区：同一张单被并发提交时，查状态和改状态必须原子完成
        self.write_lock = threading.Lock()
        for module, key in UNIQUE_KEYS.items():
            self._tables[module] = self.dedupe(self._tables.get(module, []), key)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    @staticmethod
    def dedupe(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        """按业务唯一键去重：同一张单只保留第一次出现的记录。"""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for row in rows:
            marker = str(row.get(key) or "").strip() or f"#{row.get('id', '')}"
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(row)
        return unique

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
