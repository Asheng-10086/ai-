"""养成系统：用户好感度档案 + 关系阶段划分。

- UserProfile 表：存每个用户的好感度 / 经验 / 等级 / 心情等数值。
- STAGES：把好感度映射到关系阶段，用于后续驱动动态人设。
"""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import get_session, Model


# ============ 用户档案表 ============

class UserProfile(Model):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)

    affection: Mapped[int] = mapped_column(Integer, default=0)   # 好感度（核心数值）
    exp: Mapped[int] = mapped_column(Integer, default=0)          # 成长经验值
    level: Mapped[int] = mapped_column(Integer, default=1)        # 成长等级
    mood: Mapped[int] = mapped_column(Integer, default=60)        # 角色心情 0-100

    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# ============ 关系阶段划分 ============
# 每项：(好感度下限, 阶段标识, 阶段名, 该阶段角色的表现)
STAGES = [
    (0,   "stranger", "陌生人", "对你礼貌而疏离，话不多"),
    (50,  "friend",   "朋友",   "开始亲近，会主动找你聊天"),
    (150, "close",    "挚友",   "无话不谈，会分享自己的心事和秘密"),
    (300, "intimate", "羁绊",   "对你完全信任，有专属称呼，语气亲昵"),
]


def get_stage(affection: int):
    """根据好感度返回当前阶段元组 (下限, 标识, 名称, 描述)。"""
    stage = STAGES[0]
    for s in STAGES:
        if affection >= s[0]:
            stage = s
    return stage


def build_stage_text(affection: int) -> str:
    """生成一段可注入 system prompt 的关系阶段描述。"""
    _, key, name, desc = get_stage(affection)
    return f"当前你们的关系阶段是「{name}」：{desc}。"


# ============ 档案读写 ============

async def get_profile(user_id: str) -> UserProfile:
    """读取用户档案；不存在则创建并返回。"""
    async with get_session() as session:
        profile = (
            await session.scalars(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
        ).first()
        if profile is None:
            profile = UserProfile(user_id=user_id)
            session.add(profile)
            await session.commit()
            await session.refresh(profile)  # 刷新，避免返回后属性失效
        return profile


async def add_affection(user_id: str, delta: int) -> int:
    """好感度增减（最低为 0），返回新值。"""
    async with get_session() as session:
        profile = (
            await session.scalars(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
        ).first()
        if profile is None:
            profile = UserProfile(user_id=user_id)
            session.add(profile)

        new_val = max(0, (profile.affection or 0) + delta)
        profile.affection = new_val
        profile.last_active_at = datetime.now()
        await session.commit()
        return new_val

