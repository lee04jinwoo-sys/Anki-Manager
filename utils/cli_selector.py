import sys
import tty
import termios
from rich.live import Live
from rich.table import Table
from rich.console import Console, Group
from rich.text import Text
from rich.panel import Panel
from rich.layout import Layout

class InteractiveSelector:
    def __init__(self, items, title="Select Items", help_text=None, multi_select=True, side_panel=None, bottom_panel=None):
        self.items = items
        self.title = title
        self.multi_select = multi_select
        self.side_panel = side_panel
        self.bottom_panel = bottom_panel
        if help_text:
            self.help_text = help_text
        else:
            self.help_text = "Move: ↑/↓ | Select: Space/Enter | Finish: C | Cancel: Q" if multi_select else "Move: ↑/↓ | Select: Enter | Cancel: Q"
        
        self.selected_index = 0
        self.states = [0] * len(items)
        if not multi_select:
            self.states[0] = 1 if items else 0
        else:
            self.states = [1] * len(items)

        self.console = Console()

    def _get_key(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch += sys.stdin.read(2)
            # Handle multi-byte characters for Korean IME
            elif ord(ch) >= 128:
                # If a Korean character starts, read the full sequence
                # (Simplification: just return the first byte or full char if possible)
                # In most terminal raw modes, 'ㅂ' comes as a sequence. 
                # Let's map common Korean keys manually by their behavior if needed.
                pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def _build_full_layout(self):
        # 1. Build Menu Table
        table = Table(box=None, show_header=False, pad_edge=False)
        table.add_column("Status", width=4)
        table.add_column("Item")

        # Dynamically adjust window size based on terminal height
        term_height = self.console.height
        window_size = max(5, term_height - 15) 
        
        start = max(0, self.selected_index - window_size // 2)
        end = min(len(self.items), start + window_size)
        if end - start < window_size and start > 0:
            start = max(0, end - window_size)

        for i in range(start, end):
            item = self.items[i]
            is_current = (i == self.selected_index)
            is_selected = (self.states[i] == 1)
            if self.multi_select:
                status = " [green]●[/] " if is_selected else " [grey37]○[/] "
            else:
                status = " [cyan]→[/] " if is_current else "   "
            style = "bold white on blue" if is_current else ("white" if is_selected else "grey50")
            if not self.multi_select and not is_current:
                style = "white"
            table.add_row(status, f" {item}", style=style)
            
        menu_panel = Panel(
            Group(
                table,
                Text.from_markup(f"\n [dim cyan]{self.help_text}[/]")
            ),
            title=f"[bold white]{self.title}[/]",
            border_style="bright_blue",
            expand=True
        )

        if self.side_panel:
            from rich.table import Table
            grid = Table.grid(expand=True)
            grid.add_column() # Menu
            grid.add_column() # Stats
            grid.add_row(menu_panel, self.side_panel)
            return grid
        
        return menu_panel

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
                
                # Normalize keys (Add Korean equivalents)
                # k/ㅏ: Up, j/ㅓ: Down, q/ㅂ: Quit, c/ㅊ: Confirm
                k = key.lower()
                
                if key == '\x1b[A' or k == 'k' or key == 'ㅏ': # Up
                    self.selected_index = (self.selected_index - 1) % len(self.items)
                    if not self.multi_select:
                        self.states = [0] * len(self.items)
                        self.states[self.selected_index] = 1
                elif key == '\x1b[B' or k == 'j' or key == 'ㅓ': # Down
                    self.selected_index = (self.selected_index + 1) % len(self.items)
                    if not self.multi_select:
                        self.states = [0] * len(self.items)
                        self.states[self.selected_index] = 1
                elif key in (' ', '\r'): # Space/Enter
                    if self.multi_select:
                        self.states[self.selected_index] = 1 - self.states[self.selected_index]
                    else:
                        return [self.selected_index]
                elif k == 'c' or key == 'ㅊ': # Confirm
                    if self.multi_select:
                        return [i for i, s in enumerate(self.states) if s == 1]
                elif k == 'q' or key == 'ㅂ': # Quit
                    return None
                elif k in ('1','2','3','4','5','6','7','8','9'): # Number shortcuts
                    val = int(k) - 1
                    if val < len(self.items):
                        self.selected_index = val
                        if not self.multi_select: return [val]

    @staticmethod
    def select_one(items, title="Select One", side_panel=None, bottom_panel=None):
        selector = InteractiveSelector(items, title=title, multi_select=False, side_panel=side_panel, bottom_panel=bottom_panel)
        return selector.run()
