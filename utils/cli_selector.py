import sys
import tty
import termios
from rich.live import Live
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.panel import Panel
from rich.layout import Layout
from rich.columns import Columns

class InteractiveSelector:
    def __init__(self, items, title="Select Items", help_text=None, multi_select=True, side_panel=None, bottom_panel=None, header_panel=None):
        self.items = items
        self.title = title
        self.multi_select = multi_select
        self.side_panel = side_panel
        self.bottom_panel = bottom_panel
        self.header_panel = header_panel
        self.help_text = help_text
        
        self.selected_index = 0
        self.last_action_index = -1  # Track last toggled item for "flash" effect
        if not multi_select:
            self.states = [0] * len(items)
            if items: self.states[0] = 1
        else:
            self.states = [0] * len(items)

        self.console = Console()

    def _get_key(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch += sys.stdin.read(2)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def _build_full_layout(self):
        # 1. Build Menu Table
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column("Status", width=4)
        table.add_column("Item")

        term_height = self.console.height
        window_size = max(4, term_height - 10) # More space for menu
        
        start = max(0, self.selected_index - window_size // 2)
        end = min(len(self.items), start + window_size)
        if end - start < window_size and start > 0:
            start = max(0, end - window_size)

        for i in range(start, end):
            item = self.items[i]
            is_current = (i == self.selected_index)
            is_selected = (self.states[i] == 1)
            is_flashing = (i == self.last_action_index)

            if self.multi_select:
                if is_flashing:
                    status = " [bold black]▶[/]  "
                    style = "bold black on yellow"
                elif is_current:
                    status = " [yellow]▶[/]  "
                    style = "bold white on blue"
                else:
                    status = " [bright_green]✔[/]  " if is_selected else " [grey37]✘[/]  "
                    style = "bold white on #2e3440" if not is_selected else "bold white on green"
            else:
                if is_flashing:
                    status = " [bold black]▶[/]  "
                    style = "bold black on yellow"
                elif is_current:
                    status = " [yellow]▶[/]  "
                    style = "bold white on blue"
                else:
                    status = "    "
                    style = "white"

            table.add_row(status, f"{item}", style=style)

            
        menu_panel = Panel(
            table,
            title=f"[bold white]{self.title}[/]",
            border_style="bright_cyan" if self.items else "bright_blue",
            expand=True
        )

        # 2. Construct Layout
        layout = Layout()
        
        if self.header_panel:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="main", ratio=1),
                Layout(name="footer", size=4)
            )
            layout["header"].update(self.header_panel)
        else:
            layout.split_column(
                Layout(name="main", ratio=1),
                Layout(name="footer", size=4)
            )
        
        # Side-by-side upper part
        main_grid = Table.grid(expand=True)
        main_grid.add_column()
        main_grid.add_column()
        main_grid.add_row(menu_panel, self.side_panel or Panel("통계 정보 없음", border_style="grey37"))
        
        layout["main"].update(main_grid)
        
        if self.bottom_panel:
            layout["footer"].update(self.bottom_panel)
        else:
            help_msg = "[bold]SPACE[/]: 선택  [bold]A[/]: 전체  [bold]N[/]: 취소  [bold]C[/]: 확정  [bold]Q[/]: 종료" if self.multi_select else "[bold]ENTER[/]: 선택  [bold]Q[/]: 종료"
            layout["footer"].update(Panel(help_msg, border_style="bright_cyan", title="단축키", title_align="left"))

        return layout

    def run(self):
        indices = self.run_indices()
        if indices is None: return None
        if not self.multi_select:
            return self.items[indices[0]] if indices else None
        return [self.items[i] for i in indices]

    def run_indices(self):
        if not self.items: return []
        with Live(self._build_full_layout(), console=self.console, auto_refresh=False, screen=True) as live:
            while True:
                live.update(self._build_full_layout(), refresh=True)
                key = self._get_key()
                k = key.lower()
                
                if key == '\x1b[A' or k == 'k' or key == 'ㅏ':
                    self.selected_index = (self.selected_index - 1) % len(self.items)
                    self.last_action_index = -1
                elif key == '\x1b[B' or k == 'j' or key == 'ㅓ':
                    self.selected_index = (self.selected_index + 1) % len(self.items)
                    self.last_action_index = -1
                elif key in (' ', '\r'):
                    self.last_action_index = self.selected_index
                    if self.multi_select:
                        self.states[self.selected_index] = 1 - self.states[self.selected_index]
                    else:
                        live.update(self._build_full_layout(), refresh=True)
                        import time
                        time.sleep(0.08) # Flash duration
                        return [self.selected_index]
                elif k == 'c' or key == 'ㅊ':
                    if self.multi_select:
                        return [i for i, s in enumerate(self.states) if s == 1]
                elif k == 'a' or key == 'ㅁ':
                    if self.multi_select:
                        self.states = [1] * len(self.items)
                elif k == 'n' or key == 'ㅜ':
                    if self.multi_select:
                        self.states = [0] * len(self.items)
                elif k == 'q' or key == 'ㅂ':
                    return None
                elif k in ('1','2','3','4','5','6','7','8','9'):
                    val = int(k) - 1
                    if val < len(self.items):
                        self.selected_index = val
                        if not self.multi_select: return [val]

    @staticmethod
    def select_one(items, title="Select One", side_panel=None, bottom_panel=None, header_panel=None):
        selector = InteractiveSelector(items, title=title, multi_select=False, side_panel=side_panel, bottom_panel=bottom_panel, header_panel=header_panel)
        return selector.run()
