import asyncio

from aiogram import Bot, Dispatcher


from config import TELEGRAM_TOKEN
from handlers.start import router as start_router
from handlers.quiz import router as quiz_router
from handlers.sad import router as sad_router
from handlers.relationship import router as relationship_router

from scheduler import send_good_morning

from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(sad_router)
    dp.include_router(relationship_router)
    
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        send_good_morning,
        trigger="cron",
        hour=8,
        minute=0,
        kwargs={"bot": bot}
    )

    scheduler.start()

    await dp.start_polling(bot)



if __name__ == '__main__':
    asyncio.run(main())
