import random

from aiogram import Bot

from config import HER_ID


texts = [
    "доброе утро , заяц ❤️",
    "надеюсь у тебя будет прекрасный день ☀️",
    "я просто хотел напомнить , что ты самая лучшая 🫶",
    "пусть сегодня у тебя всё получится ✨",
    "доброе утро ! я уже думаю о тебе ❤️"
]


async def send_good_morning(bot: Bot):

    random_text = random.choice(texts)

    await bot.send_message(
        chat_id=HER_ID,
        text=random_text
    )