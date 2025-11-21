# game/network/client.py

import asyncio
from typing import Any, Dict, List, Optional

import websockets
from blessed import Terminal

from game.network.packets import (
    CHAT_MESSAGE,
    HEARTBEAT_PING,
    HEARTBEAT_PONG,
    PLAYER_MOVE,
    PLAYER_CONNECT,
    PLAYER_DISCONNECT,
    SECTOR_UPDATE,
    PORT_TRADE,
    TRADE_RESULT,
    SCAN_REQUEST,
    SCAN_RESULT,
    encode_packet,
    decode_packet,
    is_heartbeat,
)

term = Terminal()


class Theme:
    BORDER = term.bold_blue
    TITLE = term.bold_cyan
    LABEL = term.bold_white
    VALUE = term.bold_green
    ERROR = term.bold_red
    INFO = term.bold_yellow


class GameClient:
    """
    Stable TradeWars client with HUD, help menu, green mode-aware command prompt,
    and richer scan display.
    """

    def __init__(self, uri: str = "ws://localhost:8765") -> None:
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

        # Player identity
        self.player_id: Optional[str] = None
        self.players: Dict[str, Dict[str, Any]] = {}

        # Sector state
        self.current_sector_id: Optional[int] = None
        self.current_sector_data: Dict[str, Any] = {}

        # UI
        self.messages: List[str] = []
        self.max_messages = 200
        self.current_input: str = ""
        self.active_window: str = "status"
        self.animating: bool = False
        self.running: bool = True

        # Redraw control
        self.needs_redraw: bool = True

    # ============================================================
    #  SEND WRAPPERS
    # ============================================================

    async def send(self, packet_type: str, payload: Dict[str, Any]) -> None:
        if self.websocket:
            await self.websocket.send(encode_packet(packet_type, payload))

    async def send_chat(self, msg: str) -> None:
        await self.send(CHAT_MESSAGE, {"message": msg})

    async def send_warp(self, sector: int) -> None:
        await self.send(PLAYER_MOVE, {"sector": sector})

    async def send_scan(self, sector=None) -> None:
        if sector is None:
            sector = self.current_sector_id
        await self.send(SCAN_REQUEST, {"sector": sector})

    async def send_port_trade(self, action: str, good: str, amount: int) -> None:
        await self.send(
            PORT_TRADE,
            {
                "action": action.upper(),
                "good": good.lower(),
                "amount": amount,
            },
        )

    async def send_heartbeat(self):
        await self.send(HEARTBEAT_PING, {})

    # ============================================================
    #  UI HELPERS
    # ============================================================

    def _me(self) -> Dict[str, Any]:
        if self.player_id and self.player_id in self.players:
            return self.players[self.player_id]
        return {}

    def get_prompt(self) -> str:
        """Return the mode-aware command prompt string."""
        # e.g. " Nav Command > ", " Comm Command > "
        return f" {self.active_window.capitalize()} Command > "

    def draw_panel(self, title: str, y: int, height: int):
        w = term.width
        print(term.move(y, 0) + Theme.BORDER("+" + "-" * (w - 2) + "+"))
        print(
            term.move(y + 1, 0)
            + Theme.BORDER("|")
            + Theme.TITLE(title.center(w - 2))
            + Theme.BORDER("|")
        )
        for i in range(height - 3):
            print(
                term.move(y + 2 + i, 0)
                + Theme.BORDER("|")
                + " " * (w - 2)
                + Theme.BORDER("|")
            )
        print(
            term.move(y + height - 1, 0)
            + Theme.BORDER("+" + "-" * (w - 2) + "+")
        )

    def draw_hud(self):
        p = self._me()
        sector = p.get("sector", self.current_sector_id or "?")
        credits = p.get("credits", 0)
        holds = p.get("holds", 0)

        hud = (
            f" PLAYER {self.player_id or '?'}   "
            f"| Sector {sector}   "
            f"| Credits {credits}   "
            f"| Holds {holds} "
        )

        print(term.move(1, 0) + Theme.TITLE(hud.ljust(term.width)))

    def draw_ui(self):
        print(term.home + term.clear)

        header = f" TradeWars 2025 – {self.active_window.upper()} "
        print(term.bold_cyan(header.center(term.width)))

        self.draw_hud()

        if self.active_window == "status":
            self.render_status()
        elif self.active_window == "nav":
            self.render_navigation()
        elif self.active_window == "comm":
            self.render_comm()
        elif self.active_window == "ship":
            self.render_ship()
        elif self.active_window == "comp":
            self.render_computer()
        elif self.active_window == "help":
            self.render_help()

        # INPUT BAR
        prompt = self.get_prompt()
        print(
            term.move(term.height - 2, 0)
            + term.bold_green(prompt)
            + self.current_input
        )

        # Place cursor at end of input
        print(
            term.move(
                term.height - 2,
                len(prompt) + len(self.current_input),
            ),
            end="",
            flush=True,
        )

    # ============================================================
    #  WINDOWS
    # ============================================================

    def render_status(self):
        self.draw_panel("PLAYER STATUS", 3, 14)
        p = self._me()
        cargo = p.get("cargo", {})

        print(
            term.move(5, 4)
            + Theme.LABEL("Credits: ").ljust(12)
            + Theme.VALUE(str(p.get("credits", 0)))
        )
        print(
            term.move(6, 4)
            + Theme.LABEL("Holds: ").ljust(12)
            + Theme.VALUE(str(p.get("holds", 0)))
        )
        print(
            term.move(7, 4)
            + Theme.LABEL("Cargo: ").ljust(12)
            + Theme.VALUE(
                f"fuel={cargo.get('fuel',0)} "
                f"ore={cargo.get('ore',0)} "
                f"equip={cargo.get('equipment',0)}"
            )
        )
        print(
            term.move(9, 4)
            + Theme.LABEL("Sector: ").ljust(12)
            + Theme.VALUE(str(p.get("sector", self.current_sector_id or "?")))
        )

    def render_navigation(self):
        self.draw_panel("NAVIGATION", 3, 16)
        sector = self.current_sector_id or self._me().get("sector", "?")
        print(
            term.move(5, 4)
            + Theme.LABEL("Current Sector: ").ljust(18)
            + Theme.VALUE(str(sector))
        )

        warps = self.current_sector_data.get("warps") or \
                self.current_sector_data.get("neighbors") or []

        print(term.move(7, 4) + Theme.LABEL("Warp Routes:"))
        if not warps:
            print(term.move(9, 6) + Theme.INFO("No warp data."))
        else:
            y = 9
            for w in warps:
                print(term.move(y, 6) + Theme.VALUE(f"→ Sector {w}"))
                y += 1

    def render_comm(self):
        h = max(12, term.height - 5)
        self.draw_panel("COMMUNICATIONS", 3, h)

        visible = h - 4
        logs = self.messages[-visible:]

        y = 5
        for m in logs:
            print(term.move(y, 4) + Theme.VALUE(m[: term.width - 8]))
            y += 1

    def render_ship(self):
        self.draw_panel("SHIP SYSTEMS", 3, 16)
        p = self._me()

        print(
            term.move(5, 4)
            + Theme.LABEL("Hull: ").ljust(14)
            + Theme.VALUE("100%")
        )
        print(
            term.move(6, 4)
            + Theme.LABEL("Engines: ").ljust(14)
            + Theme.VALUE("OK")
        )
        print(
            term.move(7, 4)
            + Theme.LABEL("Computer: ").ljust(14)
            + Theme.VALUE("Mk I")
        )
        print(
            term.move(9, 4)
            + Theme.LABEL("Sector: ").ljust(14)
            + Theme.VALUE(
                str(p.get("sector", self.current_sector_id or "?"))
            )
        )

    def render_computer(self):
        self.draw_panel("ONBOARD COMPUTER", 3, 18)

        cmds = [
            "status, nav, comm, ship, comp, help",
            "say <msg>",
            "warp <sector>",
            "scan [sector]",
            "port info",
            "port buy <good> <n>",
            "port sell <good> <n>",
            "quit",
        ]
        y = 5
        for c in cmds:
            print(term.move(y, 4) + Theme.VALUE(c))
            y += 1

    # ============================================================
    # HELP WINDOW
    # ============================================================

    def render_help(self):
        self.draw_panel("HELP & COMMAND REFERENCE", 3, term.height - 4)

        y = 5
        lines = [
            Theme.TITLE("BASIC WINDOWS:"),
            "status  - Player status window",
            "nav     - Navigation & warp routes",
            "comm    - Communication logs",
            "ship    - Ship systems",
            "comp    - Onboard computer",
            "help    - This help menu",

            "",
            Theme.TITLE("CHAT:"),
            "say <message>     - Broadcast chat",

            "",
            Theme.TITLE("MOVEMENT:"),
            "warp <sector>     - Warp to adjacent sector",
            "scan [sector]     - Scan sector (adjacent or current)",

            "",
            Theme.TITLE("PORT TRADING:"),
            "port info",
            "port buy <good> <amount>",
            "port sell <good> <amount>",

            "",
            Theme.TITLE("EXAMPLES:"),
            "say Hello there",
            "warp 5",
            "scan 22",
            "port buy ore 10",
            "port sell fuel 5",
        ]

        for line in lines:
            text = line if isinstance(line, str) else line
            print(term.move(y, 4) + str(text))
            y += 1

    # ============================================================
    #  ANIMATIONS
    # ============================================================

    async def animate_warp(self):
        self.animating = True
        try:
            for i in range(4):
                print(term.home + term.clear)
                line = "*" * (term.width + 4 * i)
                print(
                    term.move(term.height // 2, 0)
                    + Theme.INFO(line[: term.width])
                )
                await asyncio.sleep(0.005)
        finally:
            self.animating = False
            self.needs_redraw = True

    async def animate_scan(self):
        self.animating = True
        try:
            for i in range(term.width):
                print(term.home + term.clear)
                print(
                    term.move(term.height // 2, 0)
                    + Theme.INFO(" " * i + "|")
                )
                await asyncio.sleep(0.001)
        finally:
            self.animating = False
            self.needs_redraw = True

    async def animate_port(self):
        self.animating = True
        try:
            for i in range(4):
                print(term.home + term.clear)
                pad = " " * (i * 3)
                print(
                    term.move(term.height // 2, 0)
                    + Theme.VALUE(pad + "[ PORT ACCESS ]")
                )
                await asyncio.sleep(0.06)
        finally:
            self.animating = False
            self.needs_redraw = True

    # ============================================================
    #  COMMAND HANDLER
    # ============================================================

    async def handle_command(self, cmd: str):
        if not cmd:
            return

        if cmd in ("status", "nav", "comm", "ship", "comp", "help"):
            self.active_window = cmd
            self.needs_redraw = True
            return

        if cmd in ("quit", "exit", "q"):
            self.messages.append("[SYSTEM] Exiting...")
            self.running = False
            self.needs_redraw = True
            return

        if cmd.startswith("say "):
            await self.send_chat(cmd[4:])
            self.needs_redraw = True
            return

        if cmd.startswith("warp "):
            try:
                target = int(cmd.split()[1])
            except Exception:
                self.messages.append("[SYSTEM] Usage: warp <sector>")
                self.needs_redraw = True
                return

            await self.animate_warp()
            await self.send_warp(target)
            return

        if cmd.startswith("scan"):
            parts = cmd.split()
            sector = None
            if len(parts) > 1:
                try:
                    sector = int(parts[1])
                except Exception:
                    self.messages.append("[SYSTEM] Invalid sector.")
                    self.needs_redraw = True
                    return

            await self.animate_scan()
            await self.send_scan(sector)
            # Switch to comms so the user sees scan results immediately
            self.active_window = "comm"
            self.needs_redraw = True
            return

        if cmd.startswith("port"):
            parts = cmd.split()
            if len(parts) == 2 and parts[1] == "info":
                await self.animate_port()
                await self.send_port_trade("INFO", "fuel", 1)
                return

            if len(parts) == 4:
                action = parts[1]
                good = parts[2]
                try:
                    amt = int(parts[3])
                except Exception:
                    self.messages.append("[SYSTEM] Invalid amount.")
                    self.needs_redraw = True
                    return

                await self.animate_port()
                await self.send_port_trade(action, good, amt)
                return

            self.messages.append(
                "[SYSTEM] Usage: port info | port buy <good> <n>"
            )
            self.needs_redraw = True
            return

        self.messages.append(f"[SYSTEM] Unknown command: {cmd}")
        self.needs_redraw = True

    # ============================================================
    #  MAIN UI + INPUT LOOP
    # ============================================================

    async def main_loop(self):
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            try:
                while self.running:

                    if not self.animating and self.needs_redraw:
                        self.draw_ui()
                        self.needs_redraw = False

                    # Keep cursor at input field
                    prompt = self.get_prompt()
                    print(
                        term.move(
                            term.height - 2,
                            len(prompt) + len(self.current_input),
                        ),
                        end="",
                        flush=True,
                    )

                    key = term.inkey(timeout=0.05)

                    if not key:
                        await asyncio.sleep(0.01)
                        continue

                    # CTRL+C
                    if key.code == 3:
                        self.running = False
                        break

                    # BACKSPACE
                    if key.name == "KEY_BACKSPACE" or key == "\x7f" or key.code == 263:
                        if self.current_input:
                            self.current_input = self.current_input[:-1]

                            print(
                                term.move(term.height - 2, 0)
                                + term.clear_eol
                                + term.bold_green(self.get_prompt())
                                + self.current_input,
                                end="",
                                flush=True,
                            )
                        continue

                    # ENTER
                    if key in ("\n", "\r") or key.name == "KEY_ENTER":
                        cmd = self.current_input.strip().lower()
                        self.current_input = ""

                        await self.handle_command(cmd)
                        self.needs_redraw = True

                        print(
                            term.move(
                                term.height - 2,
                                len(self.get_prompt()),
                            ),
                            end="",
                            flush=True,
                        )
                        continue

                    # Regular char
                    if key.is_sequence or len(str(key)) != 1:
                        continue

                    self.current_input += str(key)

                    print(
                        term.move(term.height - 2, 0)
                        + term.clear_eol
                        + term.bold_green(self.get_prompt())
                        + self.current_input,
                        end="",
                        flush=True,
                    )

            except KeyboardInterrupt:
                self.running = False

    # ============================================================
    #  NETWORK LOOP
    # ============================================================

    async def network_loop(self):
        try:
            async for raw in self.websocket:
                p = decode_packet(raw)
                pt = p["type"]
                payload = p["payload"]

                if is_heartbeat(p):
                    continue

                if pt == PLAYER_CONNECT:
                    pid = payload["player_id"]
                    self.players.setdefault(pid, {})

                    if self.player_id is None:
                        self.player_id = pid

                    self.messages.append(f"[SYSTEM] Player connected: {pid}")
                    self.needs_redraw = True

                elif pt == PLAYER_DISCONNECT:
                    pid = payload["player_id"]
                    self.players.pop(pid, None)
                    self.messages.append(f"[SYSTEM] Player disconnected: {pid}")
                    self.needs_redraw = True

                elif pt == SECTOR_UPDATE:
                    pid = payload["player_id"]
                    state = payload["state"]
                    sector_data = payload["sector_data"]
                    self.players[pid] = state

                    if pid == self.player_id:
                        self.current_sector_id = state.get("sector")
                        self.current_sector_data = sector_data

                    self.needs_redraw = True

                elif pt == "MOVE_REJECT":
                    reason = payload.get("reason", "Unknown reason")
                    self.messages.append(f"[SYSTEM] Move rejected: {reason}")
                    self.needs_redraw = True

                elif pt == CHAT_MESSAGE:
                    pid = payload.get("player_id", "Unknown")
                    msg = payload["message"]
                    self.messages.append(f"[{pid}] {msg}")
                    self.needs_redraw = True

                elif pt == SCAN_RESULT:
                    if payload.get("success"):
                        data = payload.get("data", {})
                        self.current_sector_data = data

                        sector_num = data.get("id") or data.get("sector_id", "?")
                        warps = data.get("warps", [])
                        port = data.get("port") or {}

                        self.messages.append(f"[SCAN] Sector {sector_num}")

                        if warps:
                            self.messages.append(
                                "[SCAN] Warps: "
                                + ", ".join(str(w) for w in warps)
                            )
                        else:
                            self.messages.append("[SCAN] No warp routes.")

                        if port:
                            name = port.get("name", "Unknown Port")
                            prices = port.get("prices", {})
                            price_str = (
                                ", ".join(
                                    f"{k}={v}" for k, v in prices.items()
                                )
                                if prices
                                else "N/A"
                            )
                            self.messages.append(f"[SCAN] Port: {name}")
                            self.messages.append(
                                f"[SCAN] Prices: {price_str}"
                            )
                        else:
                            self.messages.append("[SCAN] No port present.")

                        # Other players in this sector
                        players_here = [
                            pid
                            for pid, st in self.players.items()
                            if st.get("sector") == sector_num
                            and pid != self.player_id
                        ]
                        if players_here:
                            self.messages.append(
                                "[SCAN] Players: "
                                + ", ".join(players_here)
                            )
                        else:
                            self.messages.append(
                                "[SCAN] No other players observed."
                            )

                        # Aliens placeholder
                        self.messages.append("[SCAN] Aliens: None detected")

                    else:
                        self.messages.append(
                            f"[SCAN] Failed: {payload.get('message')}"
                        )

                    self.needs_redraw = True

                elif pt == TRADE_RESULT:
                    success = payload.get("success", False)
                    msg = payload.get("message", "")
                    self.messages.append(
                        f"[PORT] {'OK' if success else 'FAIL'}: {msg}"
                    )

                    port_data = payload.get("port")
                    if port_data and port_data.get("prices"):
                        prices = port_data["prices"]
                        price_str = ", ".join(
                            f"{k}={v}" for k, v in prices.items()
                        )
                        self.messages.append(f"[PORT] Prices: {price_str}")

                    ps = payload.get("player_state")
                    if ps and self.player_id:
                        self.players[self.player_id] = ps

                    self.needs_redraw = True

                if len(self.messages) > self.max_messages:
                    self.messages = self.messages[-self.max_messages:]

        except websockets.ConnectionClosed:
            self.messages.append("[SYSTEM] Connection closed.")
            self.running = False
            self.needs_redraw = True

    # ============================================================
    #  HEARTBEAT
    # ============================================================

    async def heartbeat_loop(self):
        while self.running and self.websocket:
            try:
                await self.send_heartbeat()
            except Exception:
                pass
            await asyncio.sleep(10)

    # ============================================================
    #  ENTRY
    # ============================================================

    async def run(self):
        async with websockets.connect(self.uri) as ws:
            self.websocket = ws
            await asyncio.gather(
                self.main_loop(),
                self.network_loop(),
                self.heartbeat_loop(),
            )


if __name__ == "__main__":
    client = GameClient()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nClient shutting down...")
