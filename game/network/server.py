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
    decode_packet,
    encode_packet,
    is_heartbeat,
    SCAN_REQUEST,       
    SCAN_RESULT, 
)

# --------------------------------------------
# SAVE / LOAD
# --------------------------------------------

AUTO_SAVE_INTERVAL = 300  # seconds (5 minutes)
SAVE_DIR = "saves"
os.makedirs(SAVE_DIR, exist_ok=True)


def save_galaxy(galaxy: Galaxy) -> None:
    path = os.path.join(SAVE_DIR, "galaxy.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(galaxy.to_dict(), f, indent=2)
    print("[AUTO-SAVE] Galaxy saved.")


def load_galaxy() -> Galaxy:
    path = os.path.join(SAVE_DIR, "galaxy.json")
    if not os.path.exists(path):
        print("[LOAD] No saved galaxy found — generating new one.")
        return Galaxy(200)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[LOAD] Loaded galaxy from {path}")
    return Galaxy.from_dict(data)


def save_players(state: Dict[str, Dict[str, Any]]) -> None:
    path = os.path.join(SAVE_DIR, "players.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print("[AUTO-SAVE] Player state saved.")


def load_players() -> Dict[str, Dict[str, Any]]:
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

_player_id_counter = itertools.count(1)


def _next_player_id() -> str:
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
    return galaxy.sectors.get(sector_id)


# -------------------------------------------------------
# Trading helpers
# -------------------------------------------------------

def _do_trade(player_id: str, action: str, good: str, amount: int) -> Dict[str, Any]:
    """Core trade logic. Returns payload for TRADE_RESULT."""
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

    if not isinstance(sector.port, Port):
        return {
            "success": False,
            "message": "Invalid port configuration.",
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
# Connection handler
# -------------------------------------------------------

async def handle_connection(websocket: WebSocketServerProtocol, path: str) -> None:  # noqa: ARG001
    player_id = _next_player_id()
    connected_players[player_id] = websocket

    # Starting state for this session
    player_state[player_id] = {
        "sector": START_SECTOR,
        "credits": 1000,
        "holds": 100,
        "cargo": {"fuel": 0, "ore": 0, "equipment": 0},
    }

    print(f"[SERVER] Player connected: {player_id}")

    # Announce connection ONCE to everyone
    await broadcast(
        encode_packet(PLAYER_CONNECT, {"player_id": player_id})
    )

    # Send INITIAL sector state only to THIS player
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


    # Main receive loop for this player
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

            # SCAN REQUEST  ---------------------------------------------------
            if packet_type == SCAN_REQUEST:
                target = payload.get("sector")
                current = player_state[player_id]["sector"]

                if target is None:
                    await websocket.send(encode_packet(
                        SCAN_RESULT,
                        {"success": False, "message": "No sector provided."}
                    ))
                    continue

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

            
    except Exception as exc:
        print(f"[SERVER ERROR] {exc}")

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
    async with serve(handle_connection, "localhost", 8765):
        print("Server running on ws://localhost:8765")
        # Run game loop + autosave in parallel
        await asyncio.gather(game_loop(), autosave_loop())


if __name__ == "__main__":
    asyncio.run(main())
