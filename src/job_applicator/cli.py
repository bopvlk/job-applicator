"""Console script for job_applicator."""

import typer
from rich.console import Console

from job_applicator import utils

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Console script for job_applicator."""
    console.print("Replace this message by putting your code into job_applicator.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
