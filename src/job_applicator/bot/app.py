import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from job_applicator.bot.handlers.auth import router as auth_router
from job_applicator.config import config
from job_applicator.storage.db import init_db
from job_applicator.storage.dedup import init_qdrant

bot = Bot(token=config.telegram_token)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(auth_router)


async def main() -> None:
    init_db()
    init_qdrant()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
