import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from job_applicator.bot.handlers.auth import router as auth_router
from job_applicator.bot.handlers.jobs import router as jobs_router
from job_applicator.clients import bot
from job_applicator.storage.db import init_db
from job_applicator.storage.dedup import init_qdrant

logger = logging.getLogger(__name__)

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(auth_router)
dp.include_router(jobs_router)


async def set_bot_commands(bot_instance: Bot) -> None:
    """Register command list in Telegram menu button."""
    commands = [
        BotCommand(command="search_now", description="⚡ Trigger live job search right now"),
        BotCommand(command="profile", description="👤 View candidate profile & stats"),
        BotCommand(command="upload_resume", description="📄 Scan PDF resume via Gemini AI"),
        BotCommand(command="set_title", description="🎯 Change target job role"),
        BotCommand(command="status", description="📊 View search status & settings"),
        BotCommand(command="stop", description="🛑 Pause search notifications"),
    ]
    await bot_instance.set_my_commands(commands)
    logger.info(
        "Telegram bot menu commands registered", extra={"event": "bot_commands_registered", "count": len(commands)}
    )


async def main() -> None:
    init_db()
    await init_qdrant()
    await set_bot_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
