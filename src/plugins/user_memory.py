import json
from nonebot_plugin_orm import get_session, Model
from sqlalchemy import String, Text, DateTime, select,Integer
from sqlalchemy.orm import Mapped, mapped_column
from collections import defaultdict, deque
from datetime import datetime

from openai import AsyncOpenAI
from nonebot import get_driver

client = AsyncOpenAI(
    api_key=getattr(get_driver().config, "deepseek_api_key", ""),
    base_url="https://api.deepseek.com",
)

MAX_HISTORY = 20      # 短期记忆窗口


turn_count = defaultdict(int)   # 每个用户累计聊了几轮
background_tasks = set()        # 保存后台任务引用，防止被回收

#====对用户记忆进行提炼，成长感的核心要素======#

#新增用户记忆数据库表
class UserMemory(Model):
    __tablename__ = "user_memory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    fact: Mapped[str] = mapped_column(Text)              # 一句话事实
    importance: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


#存记忆
async def save_memory(user_id: str, fact: str, importance: int) -> None:
    """存一条记忆，重复的 fact 自动跳过。"""
    async with get_session() as session:
        dup = (
            await session.scalars(
                select(UserMemory).where(
                    UserMemory.user_id == user_id, UserMemory.fact == fact
                )
            )
        ).first()
        if dup is None:
            session.add(UserMemory(user_id=user_id, fact=fact, importance=importance))
            await session.commit()

#读取最重要的k条记忆
async def load_top_memories(user_id: str, limit: int) -> list[UserMemory]:
    """取该用户最重要的 top-K 条记忆。"""
    async with get_session() as session:
        return list(
            (
                await session.scalars(
                    select(UserMemory)
                    .where(UserMemory.user_id == user_id)
                    .order_by(UserMemory.importance.desc(), UserMemory.id.desc())
                    .limit(limit)
                )
            ).all()
        )
    
DISTILL_SYSTEM = "你是一个记忆管家，负责从聊天记录中提炼值得长期记住的事实。"

DISTILL_PROMPT = """从下面的对话中提取关于用户、或你们两人关系、值得长期记住的事实。
每条给 fact（一句话，客观简洁）和 importance（1-10 的整数，越高越重要）。
没有值得记的就返回空列表。用 JSON 返回，格式：
{"facts": [{"fact": "用户养了一只叫团子的布偶猫", "importance": 8}]}

对话：
{transcript}"""


#提炼关键记忆
async def distill(uid: str, history: list[dict[str, str]]) -> None:
    transcript = "\n".join(
        f"{m['role']}: {m['content']}" for m in history if m.get("content")
    )
    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": DISTILL_SYSTEM},
                {"role": "user", "content": DISTILL_PROMPT.format(transcript=transcript)},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        for item in data.get("facts", []):
            fact = str(item.get("fact", "")).strip()
            importance = int(item.get("importance", 5))
            if fact:
                await save_memory(uid, fact, importance)
    except Exception:
        pass


def build_system(memories_list: list[UserMemory],persona : str) -> str:
    system = persona
    if memories_list:
        facts = "\n".join(f"- {m.fact}" for m in memories_list)
        system += (
            f"\n\n以下是你和这位用户之间值得记住的事：\n{facts}\n"
            "（带着这些记忆自然回复，不要刻意复述。）"
        )
    return system