import asyncio
import logging

import typer
from rich.console import Console

from job_applicator.bot.app import bot, dp, set_bot_commands
from job_applicator.scheduler import start_scheduler
from job_applicator.storage.db import init_db
from job_applicator.storage.dedup import init_qdrant

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

app = typer.Typer()
console = Console()


async def boot_app() -> None:
    """Initialize databases, start APScheduler, and launch Telegram Bot polling."""
    console.print("[bold green]🚀 Booting Job Applicator AI...[/bold green]")

    # 1. Initialize databases
    init_db()
    await init_qdrant()

    # 2. Register Telegram command menu
    await set_bot_commands(bot)

    # 3. Start background scheduler
    start_scheduler()
    console.print("[bold blue]⏰ APScheduler loop started.[/bold blue]")

    # 4. Start Telegram bot
    console.print("[bold magenta]🤖 Telegram Bot listening for commands...[/bold magenta]")
    await dp.start_polling(bot)


@app.command()
def main() -> None:
    """Main CLI entrypoint for Job Applicator AI."""
    asyncio.run(boot_app())


if __name__ == "__main__":
    app()
