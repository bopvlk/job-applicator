import asyncio
import logging

import typer
from rich.console import Console

from job_applicator.bot.app import bot, dp, set_bot_commands
from job_applicator.scheduler import start_scheduler
from job_applicator.storage.db import init_db
from job_applicator.storage.dedup import init_qdrant
from job_applicator.observability import init_sentry, setup_logging

# 1. Initialize structured JSON logging
setup_logging(level="INFO")
logger = logging.getLogger(__name__)

app = typer.Typer()
console = Console()


async def boot_app() -> None:
    """Initialize databases, start APScheduler, and launch Telegram Bot polling."""
    init_sentry()
    logger.info(
        "Booting Job Applicator AI...",
        extra={"event": "app_startup", "component": "core"},
    )

    logger.info("Booting Job Applicator AI...", extra={"event": "app_startup", "component": "core"})
    # 1. Initialize databases
    init_db()
    await init_qdrant()
    logger.info("Databases initialized successfully", extra={"event": "databases_ready", "component": "storage"})

    # 2. Register Telegram command menu
    await set_bot_commands(bot)

    # 3. Start background scheduler
    start_scheduler()
    logger.info("APScheduler background loop started", extra={"event": "scheduler_started", "component": "scheduler"})

    # 4. Start Telegram bot
    logger.info("Telegram Bot listening for incoming updates", extra={"event": "bot_listening", "component": "bot"})
    await dp.start_polling(bot)


@app.command()
def main() -> None:
    """Main CLI entrypoint for Job Applicator AI."""
    asyncio.run(boot_app())


if __name__ == "__main__":
    app()
