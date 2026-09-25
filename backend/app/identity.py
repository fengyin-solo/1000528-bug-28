"""账号与归属：给验收、器材这类有归属约束的动作提供「谁在操作」的判断依据。

真实项目里这里会换成统一登录与权限中心；当前用一份内置账号表，前端在
请求头 X-Operator 里带上当前账号名，后端按名字解析角色与所属工区。
读接口对所有人开放，写接口由各业务服务按归属自行把关。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

OPERATOR_HEADER = "X-Operator"
DEFAULT_OPERATOR = "值班管理员"

ROLE_ADMIN = "管理员"
ROLE_DISPOSER = "处置人员"
ROLE_ACCEPTOR = "验收人员"
ROLE_GUEST = "访客"

# 账号名 -> 角色 / 所属工区；前端切换账号的选项与这里保持一致
ACCOUNTS: dict[str, dict[str, str]] = {
    "值班管理员": {"role": ROLE_ADMIN, "section": "信号一工区"},
    "李处置": {"role": ROLE_DISPOSER, "section": "信号一工区"},
    "王验收": {"role": ROLE_ACCEPTOR, "section": "信号一工区"},
    "赵验收": {"role": ROLE_ACCEPTOR, "section": "信号二工区"},
    "孙处置": {"role": ROLE_DISPOSER, "section": "信号二工区"},
}


@dataclass(frozen=True)
class Operator:
    """当前操作人；查无此账号时 known=False，业务写操作按只读访客拒绝。"""

    name: str
    role: str
    section: str | None
    known: bool


def resolve_operator(name: str | None) -> Operator:
    """按请求头里的账号名解析操作人；没带时按默认值班账号处理，便于直连接口。

    账号名是中文，前端用 encodeURIComponent 编码后放进请求头，这里先解码再查表。
    """
    if name:
        name = unquote(name)
    else:
        name = DEFAULT_OPERATOR
    account = ACCOUNTS.get(name)
    if account is None:
        return Operator(name=name, role=ROLE_GUEST, section=None, known=False)
    return Operator(name=name, role=account["role"], section=account["section"], known=True)
