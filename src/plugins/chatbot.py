import asyncio
from collections import defaultdict, deque
from datetime import datetime
from sqlalchemy import String, Text, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import get_session, Model
from nonebot import get_driver, on_message
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from openai import AsyncOpenAI
from src.plugins import user_memory,user_growth,interaction,chat_memory

PERSONA = "你叫牧之原翔子，是一位温柔又坚强的女孩，正在慢慢长大。用自然的中文短句回复。"
TOP_K = 50             # 每次注入 prompt 的长期记忆条数
DISTILL_EVERY = 5     # 每聊多少轮提炼一次


client = AsyncOpenAI(
    api_key=getattr(get_driver().config, "deepseek_api_key", ""),
    base_url="https://api.deepseek.com",
)



# ============ 短期记忆（内存滑动窗口） ============
# 每个用户一份对话历史，最多保留 MAX_HISTORY 条消息（超出自动淘汰最旧的）
MAX_HISTORY = 20  # 约 10 轮对话；想记更多就调大，注意别超上下文长度
memories = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
loader_users : set[str] = set()  # 记录已经从数据库加载过的用户，避免重复加载
turn_count = defaultdict(int)
background_tasks = set()

#不同关系阶段存取记忆的数量
STAGE_MEMORY_LIMIT = {
    "陌生人": TOP_K,
    "朋友": 2*TOP_K,
    "挚友": 6*TOP_K,
    "羁绊": 20*TOP_K,
}

chat = on_message(rule=to_me(), priority=10, block=True)


@chat.handle()
async def handle(bot: Bot, event: MessageEvent):
    text = event.get_plaintext().strip()
    if not text:
        await chat.finish()

    # 取出这个用户自己的记忆（私聊按用户，群聊也按每个 @ 他的人分开记）
    uid = str(event.user_id)
    history = memories[uid]

    #该用户第一次出现
    if uid not in loader_users:
        loader_users.add(uid)
        for item in await chat_memory.load_memory(uid, n=MAX_HISTORY):
            history.append(item)

    #好感度提升并判断是否进入下一个阶段
    before = await user_growth.get_profile(uid)#读取用户的未对话前的档案
    new_affection = await user_growth.add_affection(uid, 1)#用户好感度加一，返回新的好感度值
    old_stage = user_growth.get_stage(before.affection)
    new_stage = user_growth.get_stage(new_affection)

    

    upgrade_hint = ""
    if new_stage[0] > old_stage[0]:  # 阶段下限变大 = 升级了
        old_memories = await user_memory.load_top_memories(uid, 3)
        recall = "\n".join(f"- {m.fact}" for m in old_memories) if old_memories else "（你们还没有太多共同回忆）"
        upgrade_hint = (
            f"\n\n【关系升级】你们的关系刚刚从「{old_stage[2]}」升为「{new_stage[2]}」。"
            f"请在回复中自然地回顾你们之间的往事，比如：\n{recall}"
        )

    #拼接对应阶段的系统提示词，以达到不同好感度不同语气的回答
    stage_name = new_stage[2]
    top = await user_memory.load_top_memories(uid, STAGE_MEMORY_LIMIT.get(stage_name, TOP_K))
    system = user_memory.build_system(top, PERSONA)
    system += "\n\n" + user_growth.build_stage_text(new_affection)
    if upgrade_hint:
        system += upgrade_hint

    if before.mood < 30:
        system += "\n\n（翔子现在心情低落，回复里透着疲惫和沮丧。）"
    elif before.mood > 80:
        system += "\n\n（翔子现在心情很好，语气活泼开心。）"

    #如果超过三天没有互动，触发特殊回复
    days_away = (datetime.now() - before.last_active_at).days if before.last_active_at else 0
    if days_away >= 3:
        system += f"\n\n（你们已经 {days_away} 天没见了，翔子很想你，回复里要流露出思念和重逢的开心。）"

    try:
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                *list(history),  # 把之前记住的对话拼进 prompt
                {"role": "user", "content": text},
            ],
        )
        reply = resp.choices[0].message.content
    except Exception as e:
        reply = f"呜，出错了：{e}"

    # 把这一轮也写进记忆
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    await chat_memory.save_memory(uid, "user", text)
    await chat_memory.save_memory(uid, "assistant", reply)

    #记忆提炼的逻辑
    turn_count[uid] += 1
    if turn_count[uid] >= DISTILL_EVERY:
        turn_count[uid] = 0
        task = asyncio.create_task(user_memory.distill(uid, list(history)))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        
    #随机事件，偶尔出现
    extra = await interaction.roll_random_event(uid)
    if extra:
        reply = reply + "\n\n" + extra

    await chat.finish(reply)
