import asyncio
import typer
from rich.console import Console

from job_applicator.bot.app import bot, dp
from job_applicator.storage.db import init_db
from job_applicator.storage.dedup import init_qdrant
from job_applicator.scheduler import start_scheduler

app = typer.Typer()
console = Console()


async def boot_app() -> None:
    """Initialize databases, start APScheduler, and launch Telegram Bot polling."""
    console.print("[bold green]🚀 Booting Job Hunter AI...[/bold green]")
    
    # 1. Initialize databases
    init_db()
    await init_qdrant()
    
    # 2. Start background scheduler
    start_scheduler()
    console.print("[bold blue]⏰ APScheduler loop started.[/bold blue]")
    
    # 3. Start Telegram bot
    console.print("[bold magenta]🤖 Telegram Bot listening for commands...[/bold magenta]")
    await dp.start_polling(bot)


@app.command()
def main() -> None:
    """Main CLI entrypoint for Job Hunter AI."""
    asyncio.run(boot_app())


if __name__ == "__main__":
    app()