"""互动行为系统：签到 / 喂食 / 陪玩 / 送礼物 + 随机事件。"""

import random
from datetime import datetime

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message
from sqlalchemy import String, Integer, Text, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import get_session, Model

from src.plugins import user_growth,user_memory

#互动事件记录表
class UserEvent(Model):
    __tablename__ = "user_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32))      # checkin / feed / play / gift / random_event
    detail: Mapped[str] = mapped_column(Text, default="")     # 详情，如礼物名
    affection_delta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

#事件记录
async def log_event(user_id: str, event_type: str, detail: str = "", delta: int = 0) -> None:
    async with get_session() as session:
        session.add(UserEvent(user_id=user_id, event_type=event_type,
                              detail=detail, affection_delta=delta))
        await session.commit()


#互动的回复模板
CHECKIN_REPLIES = [
    "早呀～今天也来签到啦，好开心！",
    "哼，今天怎么这么晚才来。",
    "签到成功！今天也要一起加油哦。",
]
FEED_REPLIES = [
    "啊——真好吃！谢谢你。",
    "呜…被投喂了，好幸福。",
    "吃饱啦，感觉浑身都是力气！",
]
PLAY_REPLIES = [
    "好耶！陪你玩最开心了！",
    "嘿嘿，今天想玩什么呀？",
    "玩累啦，但特别开心。",
]
GIFT_REPLIES = [
    "哇，是{item}！我超喜欢的！",
    "收到{item}啦，会好好珍藏的～",
    "这是送给我的{item}吗？谢谢你，好开心！",
]

#构建回复格式
def build_reply(line: str, delta: int, new_val: int) -> str:
    stage = user_growth.get_stage(new_val)[2]
    return f"{line}\n❤️ 好感度 +{delta}（当前 {new_val}，阶段：{stage}）"

#查看是否今天已经签到过
async def already_checked_in(user_id: str) -> bool:
    """今天是否已签到（查事件日志，不改 UserProfile 表）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    async with get_session() as session:
        latest = (
            await session.scalars(
                select(UserEvent)
                .where(UserEvent.user_id == user_id, UserEvent.event_type == "checkin")
                .order_by(UserEvent.id.desc())
            )
        ).first()
    return latest is not None and latest.created_at.strftime("%Y-%m-%d") == today

# ============ 命令 ============
checkin = on_command("签到", aliases={"打卡"}, priority=1, block=True)
feed = on_command("喂食", priority=1, block=True)
play = on_command("陪玩", priority=1, block=True)
gift = on_command("送礼物", priority=1, block=True)

@checkin.handle()
async def handle_checkin(bot: Bot, event: MessageEvent):
    uid =  str(event.user_id)
    
    if await already_checked_in(uid):
        await checkin.finish("今天已经签到过啦，明天再来吧～")

    new_val = await user_growth.add_affection(uid, 2)  # 签到加 2 好感度

    await log_event(uid, "checkin", delta=2)
    await checkin.finish(build_reply(random.choice(CHECKIN_REPLIES), 2, new_val))

@feed.handle()
async def handle_feed(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)
    new_val = await user_growth.add_affection(uid, 3)
    await log_event(uid, "feed", delta=3)
    await feed.finish(build_reply(random.choice(FEED_REPLIES), 3, new_val))


@play.handle()
async def handle_play(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)
    new_val = await user_growth.add_affection(uid, 4)
    await log_event(uid, "play", delta=4)
    await play.finish(build_reply(random.choice(PLAY_REPLIES), 4, new_val))

@gift.handle()
async def handle_gift(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)
    item = args.extract_plain_text().strip()
    if not item:
        await gift.finish("想送我什么呀？比如 /送礼物 巧克力")

    new_val = await user_growth.add_affection(uid, 5)
    await log_event(uid, "gift", detail=item, delta=5)
    await user_memory.save_memory(uid, f"用户送给翔子{item}", importance=6)

    await gift.finish(build_reply(random.choice(GIFT_REPLIES).format(item=item), 5, new_val))

#=======随机事件=========

RANDOM_EVENT_PROB = 0.05   # 每次聊天有 5% 概率触发，可调

RANDOM_EVENTS = [
    {"text": "（翔子突然抬起头）啊，我突然想起一件开心的事，想跟你分享！", "delta": 2},
    {"text": "对了对了，我差点忘了告诉你，今天路边的花开了，好漂亮。", "delta": 1},
    {"text": "（翔子歪着头）嗯…我好像想起来，你是不是说过喜欢喝咖啡呀？", "delta": 2},
]


async def roll_random_event(uid: str) -> str | None:
    """按概率返回一段随机事件文本，顺带 +好感、记日志；没触发返回 None。"""
    if random.random() > RANDOM_EVENT_PROB:
        return None
    ev = random.choice(RANDOM_EVENTS)
    await user_growth.add_affection(uid, ev["delta"])
    await log_event(uid, "random_event", ev["text"], ev["delta"])
    return ev["text"]