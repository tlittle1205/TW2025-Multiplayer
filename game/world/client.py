# game/network/client.py
"""
TradeWars 2025 terminal client with full-screen interface.

Features:
- Real-time multiplayer networking
- Terminal UI with multiple windows (status, nav, comm, ship, comp)
- Stardock docking with interactive services
- Port trading system
- Sector scanning and navigation
"""

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
    DOCK_REQUEST,
    DOCK_RESULT,
    DOCK_ACTION,
    MOVE_REJECT,
    encode_packet,
    decode_packet,
    is_heartbeat,
)

term = Terminal()


class Theme:
    """Color scheme for terminal UI."""
    BORDER = term.bold_blue
    TITLE = term.bold_cyan
    LABEL = term.bold_white
    VALUE = term.bold_green
    ERROR = term.bold_red
    INFO = term.bold_yellow
    SUCCESS = term.bold_green
    WARNING = term.bold_yellow


class GameClient:
    """
    TradeWars 2025 game client with terminal interface.
    
    Manages network communication, UI rendering, and user input.
    """

    def __init__(self, uri: str = "ws://localhost:8765") -> None:
        """
        Initialize game client.
        
        Args:
            uri: WebSocket server URI
        """
        self.uri = uri
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

        # Player identity
        self.player_id: Optional[str] = None
        self.players: Dict[str, Dict[str, Any]] = {}

        # Sector state
        self.current_sector_id: Optional[int] = None
        self.current_sector_data: Dict[str, Any] = {}

        # UI state
        self.messages: List[str] = []
        self.max_messages = 200
        self.current_input: str = ""
        self.active_window: str = "status"
        self.animating: bool = False
        self.running: bool = True
        self.needs_redraw: bool = True

        # Dock state
        self.in_dock: bool = False
        self.dock_menu: List[str] = []
        self.dock_intro: Optional[str] = None

    # ============================================================
    # NETWORK - SEND HELPERS
    # ============================================================

    async def send(self, packet_type: str, payload: Dict[str, Any]) -> None:
        """Send a packet to the server."""
        if self.websocket:
            await self.websocket.send(encode_packet(packet_type, payload))

    async def send_chat(self, msg: str) -> None:
        """Send a chat message."""
        await self.send(CHAT_MESSAGE, {"message": msg})

    async def send_warp(self, sector: int) -> None:
        """Request warp to another sector."""
        await self.send(PLAYER_MOVE, {"sector": sector})

    async def send_scan(self, sector: Optional[int] = None) -> None:
        """Request sector scan."""
        if sector is None:
            sector = self.current_sector_id
        await self.send(SCAN_REQUEST, {"sector": sector})

    async def send_port_trade(self, action: str, good: str, amount: int) -> None:
        """Send port trade request."""
        await self.send(
            PORT_TRADE,
            {"action": action.upper(), "good": good.lower(), "amount": amount},
        )

    async def send_dock_request(self) -> None:
        """Request docking at stardock."""
        await self.send(DOCK_REQUEST, {})

    async def send_dock_action(self, action: str) -> None:
        """Send stardock service action."""
        await self.send(DOCK_ACTION, {"action": action})

    async def send_heartbeat(self) -> None:
        """Send heartbeat ping."""
        await self.send(HEARTBEAT_PING, {})

    # ============================================================
    # UI - HELPER METHODS
    # ============================================================

    def _me(self) -> Dict[str, Any]:
        """Get current player's state."""
        if self.player_id and self.player_id in self.players:
            return self.players[self.player_id]
        return {}

    def draw_panel(self, title: str, y: int, height: int) -> None:
        """Draw a bordered panel with title."""
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

    # ============================================================
    # UI - MAIN DRAW
    # ============================================================

    def draw_ui(self) -> None:
        """Render the entire UI."""
        print(term.home + term.clear)

        # HEADER
        if self.in_dock:
            header = " TRADEWARS 2025 – STARDOCK "
        else:
            header = f" TRADEWARS 2025 – {self.active_window.upper()} "
        print(term.bold_cyan(header.center(term.width)))

        if self.in_dock:
            self.render_dock()
        else:
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

        # INPUT PROMPT
        if self.in_dock:
            prompt = "Dock Command > "
        else:
            prompt = f"{self.active_window.capitalize()} Command > "

        print(
            term.move(term.height - 2, 0)
            + term.bold_green(prompt)
            + self.current_input
        )

        print(
            term.move(
                term.height - 2, len(prompt) + len(self.current_input)
            ),
            end="",
            flush=True,
        )

    # ============================================================
    # UI - WINDOW RENDERERS
    # ============================================================

    def render_status(self) -> None:
        """Render player status window."""
        self.draw_panel("PLAYER STATUS", 2, 16)
        p = self._me()
        cargo = p.get("cargo", {})

        print(
            term.move(4, 4)
            + Theme.LABEL("Credits: ")
            + Theme.VALUE(f"{p.get('credits', 0):,}")
        )
        print(
            term.move(5, 4)
            + Theme.LABEL("Bank: ")
            + Theme.VALUE(f"{p.get('bank', 0):,}")
        )
        print(
            term.move(6, 4)
            + Theme.LABEL("Holds: ")
            + Theme.VALUE(str(p.get("holds", 0)))
        )
        print(
            term.move(7, 4)
            + Theme.LABEL("Cargo: ")
            + Theme.VALUE(str(cargo))
        )
        print(
            term.move(9, 4)
            + Theme.LABEL("Hull: ")
            + Theme.VALUE(f"{p.get('hull', 100)}%")
        )
        print(
            term.move(10, 4)
            + Theme.LABEL("Shields: ")
            + Theme.VALUE(str(p.get("shields", 10)))
        )
        print(
            term.move(12, 4)
            + Theme.LABEL("Sector: ")
            + Theme.VALUE(str(p.get("sector", self.current_sector_id or "?")))
        )

    def render_navigation(self) -> None:
        """Render navigation window."""
        self.draw_panel("NAVIGATION", 2, 18)
        sector = self.current_sector_id or self._me().get("sector", "?")
        print(
            term.move(4, 4)
            + Theme.LABEL("Current Sector: ")
            + Theme.VALUE(str(sector))
        )

        warps = (
            self.current_sector_data.get("neighbors")
            or self.current_sector_data.get("warps")
            or []
        )
        print(term.move(6, 4) + Theme.LABEL("Warp Routes:"))
        if not warps:
            print(term.move(8, 6) + Theme.INFO("No warp data."))
        else:
            y = 8
            for w in warps:
                print(term.move(y, 6) + Theme.VALUE(f"→ Sector {w}"))
                y += 1

        if self.current_sector_data.get("stardock"):
            print(term.move(y + 1, 4) + Theme.SUCCESS("[Stardock present - type 'dock']"))
        elif self.current_sector_data.get("has_port"):
            pn = self.current_sector_data.get("port_name") or "Unnamed Port"
            print(term.move(y + 1, 4) + Theme.INFO(f"Port: {pn}"))

    def render_comm(self) -> None:
        """Render communications window."""
        h = max(12, term.height - 4)
        self.draw_panel("COMMUNICATIONS", 2, h)
        visible = h - 4
        logs = self.messages[-visible:]
        y = 4
        for m in logs:
            print(term.move(y, 4) + Theme.VALUE(m[: term.width - 8]))
            y += 1

    def render_ship(self) -> None:
        """Render ship systems window."""
        self.draw_panel("SHIP SYSTEMS", 2, 16)
        p = self._me()
        print(
            term.move(4, 4)
            + Theme.LABEL("Hull: ")
            + Theme.VALUE(f"{p.get('hull', 100)}%")
        )
        print(
            term.move(5, 4)
            + Theme.LABEL("Shields: ")
            + Theme.VALUE(str(p.get("shields", 10)))
        )
        print(
            term.move(6, 4)
            + Theme.LABEL("Engines: ")
            + Theme.VALUE("OK")
        )
        print(
            term.move(7, 4)
            + Theme.LABEL("Computer: ")
            + Theme.VALUE("Mk I")
        )
        print(
            term.move(9, 4)
            + Theme.LABEL("Sector: ")
            + Theme.VALUE(str(p.get("sector", self.current_sector_id or "?")))
        )
        print(
            term.move(11, 4)
            + Theme.LABEL("Cargo Capacity: ")
            + Theme.VALUE(f"{sum(p.get('cargo', {}).values())}/{p.get('holds', 0)}")
        )

    def render_computer(self) -> None:
        """Render onboard computer help window."""
        self.draw_panel("ONBOARD COMPUTER", 2, 20)
        cmds = [
            "Windows: status, nav, comm, ship, comp",
            "",
            "Chat: say <message>",
            "Movement: warp <sector>",
            "Scanning: scan [sector]",
            "",
            "Port Trading:",
            "  port info",
            "  port buy <good> <amount>",
            "  port sell <good> <amount>",
            "",
            "Stardock: dock (when in stardock sector)",
            "",
            "Exit: quit",
        ]
        y = 4
        for c in cmds:
            print(term.move(y, 4) + Theme.VALUE(c))
            y += 1

    def render_dock(self) -> None:
        """Render stardock docking window."""
        self.draw_panel("STARDOCK // CELESTIAL BAZAAR", 2, term.height - 4)
        y = 4

        if self.dock_intro:
            for line in self.dock_intro.split("\n"):
                if y >= term.height - 6:
                    break
                print(term.move(y, 4) + Theme.INFO(line[: term.width - 8]))
                y += 1
            y += 1

        print(term.move(y, 4) + Theme.LABEL("Services:"))
        y += 2
        for line in self.dock_menu:
            if y >= term.height - 6:
                break
            print(term.move(y, 6) + Theme.VALUE(line[: term.width - 10]))
            y += 1

        print(term.move(y + 1, 4) + Theme.INFO("Type service number, or 0 to undock."))

    # ============================================================
    # ANIMATIONS
    # ============================================================

    async def animate_warp(self) -> None:
        """Warp jump animation."""
        self.animating = True
        try:
            for i in range(4):
                print(term.home + term.clear)
                line = "*" * (term.width + 4 * i)
                print(term.move(term.height // 2, 0) + Theme.INFO(line[: term.width]))
                await asyncio.sleep(0.05)
        finally:
            self.animating = False
            self.needs_redraw = True

    async def animate_scan(self) -> None:
        """Scanning animation."""
        self.animating = True
        try:
            for i in range(term.width):
                print(term.home + term.clear)
                print(
                    term.move(term.height // 2, 0)
                    + Theme.INFO(" " * i + "|")
                )
                await asyncio.sleep(0.01)
        finally:
            self.animating = False
            self.needs_redraw = True

    async def animate_port(self) -> None:
        """Port access animation."""
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
    # COMMAND HANDLER
    # ============================================================

    async def handle_command(self, cmd: str) -> None:
        """
        Process user commands.
        
        Args:
            cmd: Command string from user input
        """
        if not cmd:
            return

        # ------------------------------
        # DOCK MODE
        # ------------------------------
        if self.in_dock:
            # Numbers 0–5 are dock menu actions
            if cmd in {"0", "1", "2", "3", "4", "5"}:
                await self.send_dock_action(cmd)
                return

            # Allow text commands too
            if cmd in {"leave", "exit", "undock"}:
                await self.send_dock_action("0")
                return

            # Stardock service commands (e.g., REPAIR_HULL, BANK_DEPOSIT)
            if cmd.startswith(("repair", "upgrade", "expand", "bank", "rusty", "gamble")):
                # Parse command into action and params
                parts = cmd.split()
                action = parts[0].upper()
                
                # Map common aliases
                action_map = {
                    "REPAIR": "REPAIR_HULL",
                    "UPGRADE": "UPGRADE_SHIELDS",
                    "EXPAND": "EXPAND_CARGO",
                    "GAMBLE": "RUSTY_GAMBLE",
                }
                action = action_map.get(action, action)
                
                # Handle parameterized actions
                params = {"action": action}
                if len(parts) > 1:
                    try:
                        params["amount"] = int(parts[1])
                    except ValueError:
                        self.messages.append("[DOCK] Invalid amount.")
                        self.needs_redraw = True
                        return
                
                await self.send_dock_action(action)
                return

            self.messages.append("[DOCK] Unknown command. Use numbers 0-5 or type 'help'.")
            self.needs_redraw = True
            return

        # ------------------------------
        # NORMAL MODE
        # ------------------------------

        # Window switching
        if cmd in ("status", "nav", "comm", "ship", "comp"):
            self.active_window = cmd
            self.needs_redraw = True
            return

        # Quit
        if cmd in ("quit", "exit", "q"):
            self.messages.append("[SYSTEM] Exiting...")
            self.running = False
            self.needs_redraw = True
            return

        # Chat
        if cmd.startswith("say "):
            await self.send_chat(cmd[4:])
            self.needs_redraw = True
            return

        # Warp
        if cmd.startswith("warp "):
            parts = cmd.split()
            if len(parts) < 2:
                self.messages.append("[SYSTEM] Usage: warp <sector>")
                self.needs_redraw = True
                return
            try:
                target = int(parts[1])
            except ValueError:
                self.messages.append("[SYSTEM] Invalid sector number.")
                self.needs_redraw = True
                return

            await self.animate_warp()
            await self.send_warp(target)
            return

        # Scan
        if cmd.startswith("scan"):
            parts = cmd.split()
            sector = None
            if len(parts) > 1:
                try:
                    sector = int(parts[1])
                except ValueError:
                    self.messages.append("[SYSTEM] Invalid sector number.")
                    self.needs_redraw = True
                    return

            await self.animate_scan()
            await self.send_scan(sector)
            return

        # Port trading
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
                except ValueError:
                    self.messages.append("[SYSTEM] Invalid amount.")
                    self.needs_redraw = True
                    return

                await self.animate_port()
                await self.send_port_trade(action, good, amt)
                return

            self.messages.append("[SYSTEM] Usage: port info | port buy/sell <good> <n>")
            self.needs_redraw = True
            return

        # Docking
        if cmd == "dock":
            await self.send_dock_request()
            return

        # Debug command
        if cmd == "debug":
            self.messages.append(f"[DEBUG] Sector ID: {self.current_sector_id}")
            self.messages.append(f"[DEBUG] Sector data: {self.current_sector_data}")
            self.messages.append(f"[DEBUG] Has stardock flag: {self.current_sector_data.get('stardock')}")
            self.needs_redraw = True
            return

        self.messages.append(f"[SYSTEM] Unknown command: {cmd}")
        self.needs_redraw = True

    # ============================================================
    # MAIN UI + INPUT LOOP
    # ============================================================

    async def main_loop(self) -> None:
        """Main UI rendering and input handling loop."""
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            try:
                while self.running:

                    if not self.animating and self.needs_redraw:
                        self.draw_ui()
                        self.needs_redraw = False

                    prompt = (
                        "Dock Command > " if self.in_dock
                        else f"{self.active_window.capitalize()} Command > "
                    )

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

                            # Redraw only the input line
                            print(
                                term.move(term.height - 2, 0)
                                + term.clear_eol
                                + term.bold_green(prompt)
                                + self.current_input,
                                end="",
                                flush=True,
                            )
                        continue

                    # ENTER
                    if (
                        key == "\n"
                        or key == "\r"
                        or key.name == "KEY_ENTER"
                        or str(key) == "\r"
                        or str(key) == "\n"
                    ):
                        cmd = self.current_input.strip().lower()
                        self.current_input = ""

                        await self.handle_command(cmd)
                        self.needs_redraw = True

                        continue

                    # Regular character
                    if key.is_sequence or len(str(key)) != 1:
                        continue

                    self.current_input += str(key)

                    # Redraw input line only
                    print(
                        term.move(term.height - 2, 0)
                        + term.clear_eol
                        + term.bold_green(prompt)
                        + self.current_input,
                        end="",
                        flush=True,
                    )

            except KeyboardInterrupt:
                self.running = False

    # ============================================================
    # NETWORK LOOP
    # ============================================================

    async def network_loop(self) -> None:
        """Network message receiving and processing loop."""
        try:
            async for raw in self.websocket:
                p = decode_packet(raw)
                pt = p["type"]
                payload = p["payload"]

                # Skip heartbeat packets
                if is_heartbeat(p):
                    continue

                # Player connected
                if pt == PLAYER_CONNECT:
                    pid = payload["player_id"]
                    self.players.setdefault(pid, {})
                    if self.player_id is None:
                        self.player_id = pid
                    self.messages.append(f"[SYSTEM] Player connected: {pid}")
                    self.needs_redraw = True

                # Player disconnected
                elif pt == PLAYER_DISCONNECT:
                    pid = payload["player_id"]
                    self.players.pop(pid, None)
                    self.messages.append(f"[SYSTEM] Player disconnected: {pid}")
                    self.needs_redraw = True

                # Sector update
                elif pt == SECTOR_UPDATE:
                    pid = payload["player_id"]
                    state = payload["state"]
                    sector_data = payload["sector_data"]
                    self.players[pid] = state

                    if pid == self.player_id:
                        self.current_sector_id = state.get("sector")
                        self.current_sector_data = sector_data
                        
                        # DEBUG: Log sector data
                        if sector_data.get("stardock"):
                            self.messages.append(f"[DEBUG] Stardock detected in sector {self.current_sector_id}")
                        
                        # Exit dock mode when moving
                        self.in_dock = False
                        self.dock_intro = None
                        self.dock_menu = []

                    self.needs_redraw = True

                # Move rejected
                elif pt == MOVE_REJECT:
                    reason = payload.get("reason", "Unknown reason")
                    self.messages.append(f"[SYSTEM] Move rejected: {reason}")
                    self.needs_redraw = True

                # Chat message
                elif pt == CHAT_MESSAGE:
                    pid = payload.get("player_id", "Unknown")
                    msg = payload["message"]
                    self.messages.append(f"[{pid}] {msg}")
                    self.needs_redraw = True

                # Scan result
                elif pt == SCAN_RESULT:
                    if payload.get("success"):
                        self.current_sector_data = payload.get("data", {})
                        self.messages.append("[SCAN] Scan complete.")
                    else:
                        self.messages.append(
                            f"[SCAN] Failed: {payload.get('message')}"
                        )
                    self.needs_redraw = True

                # Trade result
                elif pt == TRADE_RESULT:
                    success = payload.get("success", False)
                    msg = payload.get("message", "")
                    status = Theme.SUCCESS("OK") if success else Theme.ERROR("FAIL")
                    self.messages.append(f"[PORT] {status}: {msg}")

                    # Update player state
                    ps = payload.get("player_state")
                    if ps and self.player_id:
                        self.players[self.player_id] = ps

                    self.needs_redraw = True

                # Dock result
                elif pt == DOCK_RESULT:
                    if payload.get("exit"):
                        # Server told us to undock
                        self.in_dock = False
                        self.dock_intro = None
                        self.dock_menu = []
                        msg = payload.get("message")
                        if msg:
                            self.messages.append(f"[DOCK] {msg}")
                        self.needs_redraw = True
                        continue

                    if payload.get("success"):
                        self.in_dock = True
                        self.dock_intro = payload.get("intro", "")
                        self.dock_menu = payload.get("menu", [])
                        self.messages.append("[DOCK] Docking successful.")
                    else:
                        self.messages.append(f"[DOCK] {payload.get('message')}")
                    self.needs_redraw = True

                # Dock action result
                elif pt == DOCK_ACTION:
                    msg = payload.get("message")
                    if msg:
                        self.messages.append(f"[DOCK] {msg}")
                    
                    # Handle multi-line responses
                    lines = payload.get("lines", [])
                    for line in lines:
                        if line:  # Skip empty lines
                            self.messages.append(f"[DOCK] {line}")
                    
                    # Update menu if provided
                    menu = payload.get("menu")
                    if isinstance(menu, list):
                        self.dock_menu = menu
                    
                    # Update player state if provided
                    ps = payload.get("player_state")
                    if ps and self.player_id:
                        self.players[self.player_id] = ps
                    
                    self.needs_redraw = True

                # Trim message history
                if len(self.messages) > self.max_messages:
                    self.messages = self.messages[-self.max_messages:]

        except websockets.ConnectionClosed:
            self.messages.append("[SYSTEM] Connection closed.")
            self.running = False
            self.needs_redraw = True
        except Exception as e:
            self.messages.append(f"[SYSTEM] Network error: {e}")
            self.running = False
            self.needs_redraw = True

    # ============================================================
    # HEARTBEAT LOOP
    # ============================================================

    async def heartbeat_loop(self) -> None:
        """Periodic heartbeat to keep connection alive."""
        while self.running and self.websocket:
            try:
                await self.send_heartbeat()
            except Exception:
                pass
            await asyncio.sleep(10)

    # ============================================================
    # ENTRY POINT
    # ============================================================

    async def run(self) -> None:
        """Connect to server and run client."""
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