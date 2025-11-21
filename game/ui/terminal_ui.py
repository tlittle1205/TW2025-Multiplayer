# game/ui/terminal_ui.py
import shutil
import textwrap
import time


# ============================================================
# ANSI Colors
# ============================================================

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BRIGHT_CYAN = "\033[96m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"


# ============================================================
# Helpers
# ============================================================

def clear():
    """Clear terminal."""
    print("\033[2J\033[H", end="")  # Clear screen & move to home


def hr(char="━", length=None):
    """Return a horizontal rule the width of the terminal."""
    width = length or shutil.get_terminal_size().columns
    return char * width


def wrap(text, width=70):
    """Word wrap for paragraphs."""
    return "\n".join(textwrap.wrap(text, width=width))


# ============================================================
# UI MAIN CLASS
# ============================================================

class TerminalUI:
    def __init__(self):
        self.last_header = None

    # --------------------------------------------------------
    # Header Bar
    # --------------------------------------------------------
    def render_header(self, player):
        """Show the TW2002-style persistent HUD."""
        clear()

        sector = player.get("sector", "?")
        credits = player.get("credits", 0)
        cargo = player.get("cargo", {})
        fuel = cargo.get("fuel", 0)

        text = (
            f" Sector: {sector}   "
            f"Credits: {credits:,}   "
            f"Fuel: {fuel}"
        )

        width = len(text) + 2

        print(C.BRIGHT_CYAN + f"┏{hr('━', width)}┓")
        print(f"┃ {text} ┃")
        print(f"┗{hr('━', width)}┛" + C.RESET)
        print()  # Space before event feed

    # --------------------------------------------------------
    # Event Log
    # --------------------------------------------------------
    def event(self, msg, color=C.WHITE):
        """Print a single event line."""
        print(color + msg + C.RESET)

    # --------------------------------------------------------
    # Big Block (for /look, /scan etc.)
    # --------------------------------------------------------
    def block(self, title, lines, color=C.CYAN):
        """Render a decorated block with a title."""
        width = max(len(title) + 4, 55)

        print(color + f"┏{hr('━', width)}┓")
        print(f"┃  {title}")
        print(f"┣{hr('━', width)}┫")

        for line in lines:
            print(f"┃  {line}")

        print(f"┗{hr('━', width)}┛" + C.RESET)
        print()

    # --------------------------------------------------------
    # Specific UI screens
    # --------------------------------------------------------

    def show_scan(self, sec):
        lines = [
            f"Sector Type : {sec['type']}",
            f"Neighbors   : {sec['neighbors']}",
            f"Port        : {'YES' if sec['port'] else 'NO'}",
            f"Planet      : {'YES' if sec['planet'] else 'NO'}",
        ]
        self.block(f"Sector {sec['id']} Scan", lines, color=C.BRIGHT_CYAN)

    def show_sector_description(self, sid, stype, neighbors, has_port, has_planet, flavor):
        lines = [
            wrap(flavor, 60),
            "",
            f"Warp Lanes : {', '.join(map(str, neighbors)) or 'None'}",
            f"Port       : {'Yes' if has_port else 'No'}",
            f"Planet     : {'Yes' if has_planet else 'No'}",
        ]
        self.block(f"Sector {sid} — {stype}", lines, color=C.CYAN)

    def show_trade_result(self, success, message, pstate):
        color = C.BRIGHT_GREEN if success else C.BRIGHT_RED
        lines = [message]

        if pstate:
            credits = pstate.get("credits", 0)
            cargo = pstate.get("cargo", {})
            lines.append(f"Credits: {credits:,}")
            lines.append(f"Cargo: {cargo}")

        self.block("Trade Result", lines, color=color)

    def alert(self, msg, level="info"):
        color = {
            "info": C.CYAN,
            "warn": C.YELLOW,
            "error": C.BRIGHT_RED,
        }.get(level, C.WHITE)

        print(color + msg + C.RESET)


# Export instance
ui = TerminalUI()
