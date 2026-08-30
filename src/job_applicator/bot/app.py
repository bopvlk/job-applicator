import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from job_applicator.bot.handlers.auth import router as auth_router
from job_applicator.bot.handlers.jobs import router as jobs_router
from job_applicator.config import config
from job_applicator.storage.db import init_db
from job_applicator.storage.dedup import init_qdrant

bot = Bot(token=config.telegram_token)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(auth_router)
dp.include_router(jobs_router)


async def set_bot_commands(bot_instance: Bot) -> None:
    """Register command list in Telegram menu button."""
    commands = [
        BotCommand(command="start", description="🚀 Start bot / authenticate"),
        BotCommand(command="set_title", description="🎯 Change target job title"),
        BotCommand(command="status", description="📊 View current search status"),
        BotCommand(command="stop", description="🛑 Pause job search notifications"),
    ]
    await bot_instance.set_my_commands(commands)


async def main() -> None:
    init_db()
    await init_qdrant()
    await set_bot_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
