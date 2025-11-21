# game/network/packets.py
"""JSON-based packet helpers for the real-time multiplayer game network layer."""

from __future__ import annotations

import json
from typing import Any, Dict

PLAYER_CONNECT = "PLAYER_CONNECT"
PLAYER_DISCONNECT = "PLAYER_DISCONNECT"
PLAYER_MOVE = "PLAYER_MOVE"
SECTOR_UPDATE = "SECTOR_UPDATE"
CHAT_MESSAGE = "CHAT_MESSAGE"
HEARTBEAT_PING = "HEARTBEAT_PING"
HEARTBEAT_PONG = "HEARTBEAT_PONG"

# New for port trading
PORT_TRADE = "PORT_TRADE"       # client -> server
TRADE_RESULT = "TRADE_RESULT"   # server -> client

SCAN_REQUEST = "SCAN_REQUEST"
SCAN_RESULT = "SCAN_RESULT"


def encode_packet(packet_type: str, payload: Dict[str, Any]) -> str:
    """Serialize a packet dictionary to a compact JSON string."""
    if not packet_type or not isinstance(packet_type, str):
        raise ValueError("packet_type must be a non-empty string")
    if payload is None or not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    packet = {"type": packet_type, "payload": payload}
    return json.dumps(packet, separators=(",", ":"), ensure_ascii=False)


def decode_packet(raw_json: str) -> Dict[str, Any]:
    """Parse a JSON string into a packet dictionary."""
    try:
        packet = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON packet") from exc

    if not isinstance(packet, dict):
        raise ValueError("Packet must be a JSON object")

    packet_type = packet.get("type")
    payload = packet.get("payload")

    if not packet_type or not isinstance(packet_type, str):
        raise ValueError("Packet missing valid 'type' field")
    if payload is None or not isinstance(payload, dict):
        raise ValueError("Packet missing valid 'payload' field")

    return packet


def is_heartbeat(packet_dict: Dict[str, Any]) -> bool:
    """Return True if the packet is a heartbeat ping/pong."""
    return packet_dict.get("type") in {HEARTBEAT_PING, HEARTBEAT_PONG}
