import asyncio
import os
from collections import defaultdict, deque
from datetime import datetime
from sqlalchemy import String, Text, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import get_session, Model
from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from openai import AsyncOpenAI


#创建记忆数据库表
class ChatMemory(Model):
    __tablename__ = "chat_memory"

    id: Mapped[int] = mapped_column(primary_key=True,autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    create_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


#将记忆写入数据库中
async def save_memory(user_id: str, role: str, content: str):
    async with get_session() as session:
        memory = ChatMemory(user_id=user_id, role=role, content=content)
        session.add(memory)
        await session.commit()

#读取数据库中最新的N条记忆
async def load_memory(user_id: str, n: int):
    async with get_session() as session:
        rows = (
            await session.scalars(
                select(ChatMemory)
                .where(ChatMemory.user_id == user_id)
                .order_by(ChatMemory.id.desc())
                .limit(n)
            )
        ).all()

        rows.reverse()
    
    return [{"role": row.role, "content": row.content} for row in rows]