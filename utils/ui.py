import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.status import Status
from rich.columns import Columns

console = Console()

class UI:
    """Modern TUI for Anki Manager using Rich (Icon-free, English)"""
    
    @staticmethod
    def clear():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def header(title="Anki Manager CLI"):
        console.print(Panel(
            Text(title, justify="center", style="bold white"),
            subtitle="[bold grey50]v2.5.0[/]",
            border_style="bright_blue",
            expand=True
        ))

    @staticmethod
    def subheader(title):
        console.print(f"\n[bold cyan]--- {title} ---[/]")

    @staticmethod
    def success(msg):
        console.print(f"[bold green][SUCCESS] {msg}[/]")

    @staticmethod
    def error(msg):
        console.print(f"[bold red][ERROR] {msg}[/]")

    @staticmethod
    def warn(msg):
        console.print(f"[bold yellow][WARN] {msg}[/]")

    @staticmethod
    def info(msg):
        console.print(f"[cyan][INFO] {msg}[/]")

    @staticmethod
    def step(msg):
        console.print(f"[yellow][STEP] {msg}[/]")

    @staticmethod
    def print(*args, **kwargs):
        console.print(*args, **kwargs)

    @staticmethod
    def divider():
        console.print("[grey50]" + "-" * 60 + "[/]")

    @staticmethod
    def table(title, columns, rows):
        table = Table(title=title, show_header=True, header_style="bold magenta", border_style="grey37")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
        console.print(table)

    @staticmethod
    def progress():
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console
        )

    @staticmethod
    def ask(msg, default=None):
        return Prompt.ask(f"[bold white][PROMPT] {msg}[/]", default=default)

    @staticmethod
    def confirm(msg, default=True):
        return Confirm.ask(f"[bold white][CONFIRM] {msg}[/]", default=default)

    @staticmethod
    def status_panel(msg, title="Status"):
        console.print(Panel(
            Text(msg, style="bold yellow"), 
            title=f"[bold white]{title}[/]", 
            border_style="yellow", 
            expand=False
        ))

    @staticmethod
    def wait(msg):
        return console.status(f"[italic grey50]{msg}...[/]")

    @staticmethod
    def display_stats(stats_data):
        """Displays deck statistics in side-by-side panels"""
        stat_cards = []
        for title, val in stats_data.items():
            card = Panel(
                Text(f"{val}", style="bold yellow", justify="center"),
                title=f"[bold white]{title}[/]",
                border_style="bright_blue",
                expand=False,
                width=25
            )
            stat_cards.append(card)
        console.print(Columns(stat_cards))
