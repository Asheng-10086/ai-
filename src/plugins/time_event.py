from datetime import datetime

from nonebot import get_bot
from nonebot_plugin_apscheduler import scheduler
from sqlalchemy import select
from nonebot_plugin_orm import get_session

from src.plugins import user_growth
from src.plugins.user_growth import UserProfile

BOT_ID = "2462238357"   #机器人qq号

# 早安文案：按关系阶段
MORNING_GREETS = {
    "陌生人": "早上好。",
    "朋友": "早安呀～今天也要加油哦。",
    "挚友": "早安！想我没？",
    "羁绊": "早安，亲爱的～今天也一起吧。",
}

EVENING_GREET = {
    "陌生人": "晚上好。",
    "朋友": "晚上好～今天也要睡个好觉哦~。",
    "挚友": "晚上好！",
    "羁绊": "晚上好，亲爱的～今天晚上也睡个好觉！。",
}

# 特殊日期：(月份, 日期, 事件文案)
SPECIAL_DATES = [
    (11, 6, "今天是翔子的生日！🎂 记得跟她说生日快乐哦～"),
    (1, 1, "新年快乐！新的一年也要一起哦。"),
    (12, 25, "圣诞快乐！送你一个大大的拥抱。"),
]

async def _bot():
    """定时任务里拿 Bot；以后多 bot 就改成遍历 get_bots().values()。"""
    return get_bot(BOT_ID)

async def _profiles():
    """获取所有用户资料"""
    async with get_session() as session:
        rows = list((await session.scalars(select(UserProfile))).all())
        return rows
    

#======1.每日心情衰减=======#
@scheduler.scheduled_job("cron", hour=0, minute=0,id = "daily_mood_decay")
async def daily_mood_decay():
    async with get_session() as session:
        profiles = list((await session.scalars(select(UserProfile))).all())
        now = datetime.now()
        changed = 0
        for p in profiles:
            if (now - p.last_active_at).days >= 1:      # 超过 1 天没互动
                p.mood = max(0, (p.mood or 60) - 10)    # 心情 -10，最低 0
                changed += 1
        if changed:
            await session.commit()

# ============ 2. 每日早安（每天 8 点） ============
@scheduler.scheduled_job("cron", hour=8, minute=0, id="morning_greet")
async def morning_greet():
    bot = await _bot()
    for p in await _profiles():
        stage_name = user_growth.get_stage(p.affection)[2]
        text = MORNING_GREETS.get(stage_name, "早安～")
        await bot.send_private_msg(user_id=int(p.user_id), message=text)


# ============ 3. 每日晚上好（每天 8 点） ============
@scheduler.scheduled_job("cron", hour=20, minute=0, id="evening_greet")
async def evening_greet():
     bot = await _bot()
     for p in await _profiles():
        stage_name = user_growth.get_stage(p.affection)[2]
        text =  EVENING_GREET.get(stage_name, "晚上好~")
        await bot.send_private_msg(user_id=int(p.user_id), message=text)


# ============ 4. 特殊日期事件（每天 9 点检查一次） ============
@scheduler.scheduled_job("cron", hour=9, minute=0, id="special_date")
async def special_date_event():
    today = datetime.now()
    for month, day, text in SPECIAL_DATES:
        if (today.month, today.day) == (month, day):
            bot = await _bot()
            for p in await _profiles():
                await bot.send_private_msg(user_id=int(p.user_id), message=text)