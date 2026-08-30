import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import Message

from job_applicator.bot.handlers.auth import router as auth_router
from job_applicator.config import load_config
from job_applicator.storage.db import init_db

config = load_config()
bot = Bot(token=config.telegram_token)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(auth_router)

async def main() -> None:
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())