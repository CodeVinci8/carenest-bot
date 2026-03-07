import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TELEGRAM_TOKEN
from database import init_db
from scheduler import send_good_morning

from handlers.start import router as start_router
from handlers.quiz import router as quiz_router
from handlers.sad import router as sad_router
from handlers.relationship import router as relationship_router
from handlers.wishlist import router as wishlist_router


async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command="start", description="запустить бота"),
        BotCommand(command="quiz", description="начать квиз"),
    ]
    await bot.set_my_commands(commands)


async def main():
    init_db()

    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(sad_router)
    dp.include_router(relationship_router)
    dp.include_router(wishlist_router)

    await set_main_menu(bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_good_morning,
        trigger="cron",
        hour=11,
        minute=0,
        kwargs={"bot": bot}
    )
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())