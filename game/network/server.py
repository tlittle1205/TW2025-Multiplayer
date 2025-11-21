# game/network/server.py

import asyncio
import itertools
import json
import os
from typing import Any, Dict

import websockets
from websockets.server import WebSocketServerProtocol, serve

from game.world.galaxy import Galaxy
from game.world.port import Port
from game.world.stardock import stardock_process_action
from game.network.packets import (
    CHAT_MESSAGE,
    HEARTBEAT_PING,
    HEARTBEAT_PONG,
    PLAYER_CONNECT,
    PLAYER_DISCONNECT,
    PLAYER_MOVE,
    SECTOR_UPDATE,
    PORT_TRADE,
    TRADE_RESULT,
    SCAN_REQUEST,
    SCAN_RESULT,
    DOCK_REQUEST,
    DOCK_RESULT,
    DOCK_ACTION,
    decode_packet,
    encode_packet,
    is_heartbeat,
)

# --------------------------------------------
# SAVE / LOAD
# --------------------------------------------

AUTO_SAVE_INTERVAL = 300  # seconds (5 minutes)
SAVE_DIR = "saves"
os.makedirs(SAVE_DIR, exist_ok=True)


def save_galaxy(galaxy: Galaxy) -> None:
    """Save galaxy state to disk."""
    path = os.path.join(SAVE_DIR, "galaxy.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(galaxy.to_dict(), f, indent=2)
    print("[AUTO-SAVE] Galaxy saved.")


def load_galaxy() -> Galaxy:
    """Load galaxy state from disk or generate new one."""
    path = os.path.join(SAVE_DIR, "galaxy.json")
    if not os.path.exists(path):
        print("[LOAD] No saved galaxy found — generating new one.")
        return Galaxy(200)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[LOAD] Loaded galaxy from {path}")
    return Galaxy.from_dict(data)


def save_players(state: Dict[str, Dict[str, Any]]) -> None:
    """Save player state to disk."""
    path = os.path.join(SAVE_DIR, "players.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print("[AUTO-SAVE] Player state saved.")


def load_players() -> Dict[str, Dict[str, Any]]:
    """Load player state from disk."""
    path = os.path.join(SAVE_DIR, "players.json")
    if not os.path.exists(path):
        print("[LOAD] No player save found — starting fresh.")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[LOAD] Loaded player state from {path}")
    return data


# -------------------------------------------------------
# WORLD
# -------------------------------------------------------

galaxy: Galaxy = load_galaxy()
START_SECTOR = 1

# -------------------------------------------------------
# PLAYER STATE
# -------------------------------------------------------

connected_players: Dict[str, WebSocketServerProtocol] = {}
player_state: Dict[str, Dict[str, Any]] = load_players()

# Initialize player ID counter based on existing saved players
if player_state:
    max_id = max(
        (int(pid.split('-')[1]) for pid in player_state.keys() if '-' in pid and pid.split('-')[1].isdigit()),
        default=0
    )
    _player_id_counter = itertools.count(max_id + 1)
else:
    _player_id_counter = itertools.count(1)


def _next_player_id() -> str:
    """Generate next unique player ID."""
    return f"player-{next(_player_id_counter)}"


async def broadcast(packet: str) -> None:
    """Broadcast an encoded packet to all connected players."""
    if not connected_players:
        return
    await asyncio.gather(
        *(ws.send(packet) for ws in connected_players.values()),
        return_exceptions=True,
    )


def _get_sector(sector_id: int):
    """Get sector by ID from galaxy."""
    return galaxy.sectors.get(sector_id)


# -------------------------------------------------------
# Trading helpers
# -------------------------------------------------------

def _do_trade(player_id: str, action: str, good: str, amount: int) -> Dict[str, Any]:
    """
    Core trade logic. Returns payload for TRADE_RESULT.
    
    Args:
        player_id: Player performing the trade
        action: Trade action (INFO, BUY, SELL)
        good: Commodity name
        amount: Quantity to trade
    
    Returns:
        Trade result payload dict
    """
    state = player_state[player_id]
    sector_id = state["sector"]
    sector = _get_sector(sector_id)

    if sector is None or sector.port is None:
        return {
            "success": False,
            "message": "No port in this sector.",
            "player_state": state,
            "port": None,
        }

    prices = sector.port.prices
    if good not in prices:
        return {
            "success": False,
            "message": f"Port does not trade '{good}'.",
            "player_state": state,
            "port": sector.port.to_dict(),
        }

    credits = state.get("credits", 0)
    holds = state.get("holds", 0)
    cargo = state.setdefault("cargo", {"fuel": 0, "ore": 0, "equipment": 0})
    
    # Ensure the good exists in cargo
    if good not in cargo:
        cargo[good] = 0

    # Normalize amount
    if amount <= 0:
        return {
            "success": False,
            "message": "Amount must be positive.",
            "player_state": state,
            "port": sector.port.to_dict(),
        }

    price_per = prices[good]

    if action == "INFO":
        return {
            "success": True,
            "message": "Port info.",
            "player_state": state,
            "port": sector.port.to_dict(),
        }

    if action == "BUY":
        total_cost = price_per * amount

        # Capacity check
        used_holds = sum(cargo.values())
        if used_holds + amount > holds:
            return {
                "success": False,
                "message": "Not enough cargo space.",
                "player_state": state,
                "port": sector.port.to_dict(),
            }

        if total_cost > credits:
            return {
                "success": False,
                "message": "Not enough credits.",
                "player_state": state,
                "port": sector.port.to_dict(),
            }

        # Apply buy
        state["credits"] = credits - total_cost
        cargo[good] = cargo.get(good, 0) + amount

        return {
            "success": True,
            "message": f"Bought {amount} {good} for {total_cost} credits.",
            "player_state": state,
            "port": sector.port.to_dict(),
        }

    if action == "SELL":
        if cargo.get(good, 0) < amount:
            return {
                "success": False,
                "message": f"Not enough {good} to sell.",
                "player_state": state,
                "port": sector.port.to_dict(),
            }

        total_gain = price_per * amount
        cargo[good] -= amount
        state["credits"] = credits + total_gain

        return {
            "success": True,
            "message": f"Sold {amount} {good} for {total_gain} credits.",
            "player_state": state,
            "port": sector.port.to_dict(),
        }

    return {
        "success": False,
        "message": f"Unknown trade action '{action}'.",
        "player_state": state,
        "port": sector.port.to_dict(),
    }


# -------------------------------------------------------
# Stardock helpers
# -------------------------------------------------------

STARDOCK_SECTOR = 2

STARDOCK_MENU = [
    "1. Corporate Concourse (Luxury Upgrades)",
    "2. Interstellar Bank (Citadel Vaults)",
    "3. The Rusty Nebula (Seedy Cantina)",
    "4. Market Promenade (Shops & Exotic Goods)",
    "5. Tech Lab (Experimental Mods)",
    "0. Return to Space",
]

STARDOCK_INTRO = (
    "Approach vector locked. Thrusters balanced.\n"
    "Your ship breaks through the swirling traffic lanes. Freighters claw for docking priority, "
    "shuttles scream past your hull, and warning klaxons erupt like gunfire.\n\n"
    "The Celestial Bazaar rises before you like a jewel carved from sin. Thousands of thrusters paint the void in "
    "gold and sapphire as ships jostle for position. Pleasure yachts glimmer beside rust-bitten smugglers, each "
    "dripping attitude. The descent is a dance—fast, sharp, and merciless. One mistake, and you become someone "
    "else's hood ornament.\n\n"
    "█████████  STARDOCK // CELESTIAL BAZAAR  █████████"
)


def _sector_is_stardock(sector_id: int) -> bool:
    """Check if sector contains a stardock."""
    sec = _get_sector(sector_id)
    return bool(sec and getattr(sec, "is_stardock", False))


def _handle_dock_action(player_id: str, action: str) -> Dict[str, Any]:
    """
    Handle basic dock menu navigation (numbers 0-5).
    Returns flavor text and menu state.
    
    Args:
        player_id: Player performing action
        action: Menu selection (0-5)
    
    Returns:
        Response dict with message, menu, and exit flag
    """
    state = player_state[player_id]
    msg = ""

    if action == "1":
        msg = "You step into the Corporate Concourse. Everything smells like credits and polished egos."
    elif action == "2":
        msg = "You enter the Interstellar Bank. It smells like ozone, old money, and quiet judgment."
    elif action == "3":
        msg = "The Rusty Nebula greets you with smoke, neon, and a band that's three drinks past tight."
    elif action == "4":
        msg = "Market Promenade: hawkers shout, holograms flicker, and something in a jar blinks back at you."
    elif action == "5":
        msg = "You walk into the Tech Lab. Sparks, arguments, and very few safety rails."
    elif action == "0":
        msg = "You undock and drift back into open space."
    else:
        msg = "The dock systems don't understand that input."

    return {
        "message": msg,
        "menu": STARDOCK_MENU,
        "exit": (action == "0"),
    }


# -------------------------------------------------------
# Connection handler
# -------------------------------------------------------

async def handle_connection(websocket: WebSocketServerProtocol, path: str) -> None:  # noqa: ARG001
    """
    Handle individual client WebSocket connection.
    
    Args:
        websocket: WebSocket connection
        path: Connection path (unused)
    """
    player_id = _next_player_id()
    connected_players[player_id] = websocket

    # Starting state for this session - includes all required fields
    player_state[player_id] = {
        "sector": START_SECTOR,
        "credits": 1000,
        "holds": 100,
        "cargo": {"fuel": 0, "ore": 0, "equipment": 0},
        "hull": 100,      # Required for stardock repairs
        "shields": 10,    # Required for stardock upgrades
        "bank": 0,        # Required for stardock banking
    }

    print(f"[SERVER] Player connected: {player_id}")

    # Announce connection
    await broadcast(
        encode_packet(PLAYER_CONNECT, {"player_id": player_id})
    )

    # Send initial sector state only to this player
    initial_sector_data = galaxy.serialize_sector(START_SECTOR)
    await websocket.send(
        encode_packet(
            SECTOR_UPDATE,
            {
                "player_id": player_id,
                "state": player_state[player_id],
                "sector_data": initial_sector_data,
            },
        )
    )

    try:
        async for message in websocket:
            packet = decode_packet(message)
            packet_type = packet["type"]
            payload = packet["payload"]

            # Heartbeat
            if is_heartbeat(packet):
                await websocket.send(encode_packet(HEARTBEAT_PONG, {}))
                continue

            # Movement
            if packet_type == PLAYER_MOVE:
                requested = payload.get("sector")
                current = player_state[player_id]["sector"]

                if requested is None:
                    await websocket.send(encode_packet("MOVE_REJECT",
                                                       {"reason": "No sector given."}))
                    continue

                if not galaxy.sector_exists(requested):
                    await websocket.send(encode_packet("MOVE_REJECT",
                                                       {"reason": "Sector does not exist."}))
                    continue

                if not galaxy.is_adjacent(current, requested):
                    await websocket.send(encode_packet("MOVE_REJECT",
                                                       {"reason": "Sector not adjacent."}))
                    continue

                # Accept movement
                player_state[player_id]["sector"] = requested
                save_players(player_state)

                await broadcast(encode_packet(
                    SECTOR_UPDATE,
                    {
                        "player_id": player_id,
                        "state": player_state[player_id],
                        "sector_data": galaxy.serialize_sector(requested),
                    }
                ))
                continue

            # Chat
            if packet_type == CHAT_MESSAGE:
                msg = payload.get("message", "")
                await broadcast(encode_packet(
                    CHAT_MESSAGE,
                    {"player_id": player_id, "message": msg}
                ))
                continue

            # Port trade
            if packet_type == PORT_TRADE:
                action = payload.get("action", "").upper()
                good = payload.get("good", "").lower()
                amount = int(payload.get("amount", 0))

                result_payload = _do_trade(player_id, action, good, amount)
                save_players(player_state)

                await websocket.send(encode_packet(TRADE_RESULT, result_payload))
                continue

            # Scan
            if packet_type == SCAN_REQUEST:
                target = payload.get("sector")
                current = player_state[player_id]["sector"]

                if target is None:
                    target = current

                if not galaxy.sector_exists(target):
                    await websocket.send(encode_packet(
                        SCAN_RESULT,
                        {"success": False, "message": "Sector does not exist."}
                    ))
                    continue

                if target != current and not galaxy.is_adjacent(current, target):
                    await websocket.send(encode_packet(
                        SCAN_RESULT,
                        {"success": False, "message": "Sector not adjacent."}
                    ))
                    continue

                sec_data = galaxy.serialize_sector(target)
                await websocket.send(encode_packet(
                    SCAN_RESULT,
                    {"success": True, "sector": target, "data": sec_data}
                ))
                continue

            # ---------------------------------------------------
            # DOCKING
            # ---------------------------------------------------

            if packet_type == DOCK_REQUEST:
                current = player_state[player_id]["sector"]

                if not _sector_is_stardock(current):
                    await websocket.send(encode_packet(
                        DOCK_RESULT,
                        {
                            "success": False,
                            "message": "No Stardock in this sector.",
                        },
                    ))
                    continue

                # Stardock exists — send intro + menu
                await websocket.send(encode_packet(
                    DOCK_RESULT,
                    {
                        "success": True,
                        "intro": STARDOCK_INTRO,
                        "menu": STARDOCK_MENU,
                    },
                ))
                continue

            if packet_type == DOCK_ACTION:
                action = str(payload.get("action", "")).strip()
                
                # Handle numeric menu selections (0-5)
                if action in {"0", "1", "2", "3", "4", "5"}:
                    result = _handle_dock_action(player_id, action)
                    
                    if result.get("exit"):
                        # Inform client to exit dock mode
                        await websocket.send(encode_packet(
                            DOCK_RESULT,
                            {
                                "success": False,
                                "message": result["message"],
                                "exit": True,
                            },
                        ))
                    else:
                        await websocket.send(encode_packet(
                            DOCK_ACTION,
                            {
                                "message": result["message"],
                                "menu": result["menu"],
                            },
                        ))
                else:
                    # Handle actual stardock actions like REPAIR_HULL, BANK_DEPOSIT, etc.
                    result = stardock_process_action(
                        action, 
                        payload, 
                        player_state[player_id], 
                        galaxy
                    )
                    
                    # Save player state if action was successful
                    if result.get("success"):
                        save_players(player_state)
                    
                    # Return result with player state update
                    await websocket.send(encode_packet(
                        DOCK_ACTION,
                        result
                    ))
                
                continue

    except websockets.ConnectionClosed:
        print(f"[SERVER] Connection closed for {player_id}")
    except Exception as exc:
        print(f"[SERVER ERROR] {player_id}: {exc}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"[SERVER] Player disconnected: {player_id}")
        connected_players.pop(player_id, None)
        player_state.pop(player_id, None)
        save_players(player_state)
        await broadcast(encode_packet(PLAYER_DISCONNECT, {"player_id": player_id}))


# -------------------------------------------------------
# Loops
# -------------------------------------------------------

async def game_loop() -> None:
    """Main game tick loop (NPCs, events, etc. in the future)."""
    while True:
        await asyncio.sleep(0.1)


async def autosave_loop() -> None:
    """Periodically autosave the galaxy and player state."""
    while True:
        await asyncio.sleep(AUTO_SAVE_INTERVAL)
        save_galaxy(galaxy)
        save_players(player_state)


async def main() -> None:
    """Start the game server."""
    async with serve(handle_connection, "localhost", 8765):
        print("=" * 60)
        print("TRADEWARS 2025 SERVER")
        print("=" * 60)
        print(f"Server running on ws://localhost:8765")
        print(f"Galaxy size: {galaxy.size} sectors")
        print(f"Stardock location: Sector {STARDOCK_SECTOR}")
        print(f"Active players: {len(player_state)}")
        print("=" * 60)
        await asyncio.gather(game_loop(), autosave_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down gracefully...")