import asyncio
from aiogram import Bot, Dispatcher


from config import TELEGRAM_TOKEN
from handlers.start import router as start_router
from handlers.quiz import router as quiz_router
from handlers.sad import router as sad_router

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(sad_router)
    
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
