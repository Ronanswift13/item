#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户与权限模型：账号登录与操作权限判断。"""

from __future__ import annotations

from dataclasses import dataclass
import enum
import hashlib
import getpass
from typing import Dict, List, Optional

__all__ = [
    "Role",
    "User",
    "hash_password",    
    "verify_password",
    "get_user",
    "authenticate",
    "has_role",
    "user_is_admin",
    "user_can_set_target_cabinet",
    "user_can_view_logs",
    "list_users",
]


class Role(enum.Enum):
    """用户角色枚举，后续可扩展更多权限等级。"""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass
class User:
    """系统用户，包含账号、显示名、密码哈希与角色信息。"""

    username: str
    display_name: str
    password_hash: str
    roles: List[Role]


# 内存中的用户表；由于是纯内存实现，进程退出后数据即消失
_USERS: Dict[str, User] = {}


def hash_password(password: str) -> str:
    """
    使用 sha256 对明文密码进行哈希，返回十六进制字符串。

    注意：生产环境应使用salt哈希或密码学库
    """

    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码是否匹配给定哈希。"""

    return hash_password(password) == password_hash


def get_user(username: str) -> Optional[User]:
    """根据用户名查找用户，不存在则返回 None。"""

    return _USERS.get(username)


def authenticate(username: str, password: str) -> Optional[User]:
    """执行用户名/密码认证，成功返回 User，失败返回 None。"""

    user = get_user(username)
    if user is None:
        return None
    if verify_password(password, user.password_hash):
        return user
    return None


def _init_default_users() -> None:
    """初始化默认演示账号，便于直接使用或测试。"""

    # 先清理旧数据，确保多次调用保持一致
    _USERS.clear()

    _USERS["Ronan"] = User(
        username="Ronan",
        display_name="管理员 Ronan",
        password_hash=hash_password("123"),
        roles=[Role.ADMIN],
    )
    _USERS["admin"] = User(
        username="admin",
        display_name="系统管理员",
        password_hash=hash_password("admin123"),
        roles=[Role.ADMIN],
    )
    _USERS["operator"] = User(
        username="operator",
        display_name="值班员",
        password_hash=hash_password("op12345"),
        roles=[Role.OPERATOR],
    )
    _USERS["viewer"] = User(
        username="viewer",
        display_name="观察者",
        password_hash=hash_password("view123"),
        roles=[Role.VIEWER],
    )


def has_role(user: User, role: Role) -> bool:
    """判断用户是否拥有某个角色；后续可扩展角色继承等复杂逻辑。"""

    return role in user.roles


def user_is_admin(user: User) -> bool:
    """是否拥有管理员权限。"""

    return has_role(user, Role.ADMIN)


def user_can_set_target_cabinet(user: User) -> bool:
    """示例策略：管理员与操作员可修改机位，观察者不允许。"""

    return has_role(user, Role.ADMIN) or has_role(user, Role.OPERATOR)


def user_can_view_logs(user: User) -> bool:
    """示例策略：所有角色均可查看日志，后续可根据需要收紧权限。"""

    return any(
        [
            has_role(user, Role.ADMIN),
            has_role(user, Role.OPERATOR),
            has_role(user, Role.VIEWER),
        ]
    )


def list_users() -> List[User]:
    """返回当前所有用户的列表，便于调试或管理界面展示。"""

    return list(_USERS.values())


def main() -> None:
    """命令行演示：交互式输入账号密码并显示权限。"""

    print("=== 用户登录测试 ===")
    username = input("用户名: ").strip()
    try:
        password = getpass.getpass("密码: ")
    except Exception:
        # 某些 IDE/终端不支持 getpass，可退回普通 input
        password = input("密码: ")

    user = authenticate(username, password)
    if not user:
        print("用户名或密码错误。")
        return

    print(f"欢迎，{user.display_name}（{user.username}）")
    role_names = ", ".join(role.name for role in user.roles)
    print(f"角色: {role_names}")
    print(f"可设置机位: {user_can_set_target_cabinet(user)}")
    print(f"可查看日志: {user_can_view_logs(user)}")
    print(f"是否管理员: {user_is_admin(user)}")


# 模块导入时初始化默认用户，方便直接调用
_init_default_users()


if __name__ == "__main__":
    # 确保默认用户存在后再进入交互式测试
    _init_default_users()
    main()