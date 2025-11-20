"""Utilities for encoding and decoding network packets.

The protocol is intentionally minimal: every packet is JSON with two fields:
"type" (string) and "payload" (object). These helpers keep validation and
serialization lightweight for asyncio transports.
"""

from __future__ import annotations

import json
from typing import Any, Dict

# Packet type constants
PLAYER_CONNECT = "PLAYER_CONNECT"
PLAYER_DISCONNECT = "PLAYER_DISCONNECT"
PLAYER_MOVE = "PLAYER_MOVE"
SECTOR_UPDATE = "SECTOR_UPDATE"
CHAT_MESSAGE = "CHAT_MESSAGE"
HEARTBEAT_PING = "HEARTBEAT_PING"
HEARTBEAT_PONG = "HEARTBEAT_PONG"


def encode_packet(packet_type: str, payload: Dict[str, Any]) -> str:
    """Encode a packet to a JSON string.

    Args:
        packet_type: Identifier for the packet.
        payload: Structured data payload; must be JSON-serializable.

    Returns:
        Compact JSON string ready for network transmission.

    Raises:
        ValueError: If inputs are malformed.
    """

    if not isinstance(packet_type, str) or not packet_type:
        raise ValueError("packet_type must be a non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    packet = {"type": packet_type, "payload": payload}
    return json.dumps(packet, separators=(",", ":"))


def decode_packet(raw_json: str) -> Dict[str, Any]:
    """Decode and validate a JSON packet string.

    Args:
        raw_json: JSON string received over the network.

    Returns:
        The decoded packet as a dictionary.

    Raises:
        ValueError: If the JSON is invalid or missing required fields.
    """

    try:
        packet = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON packet") from exc

    if not isinstance(packet, dict):
        raise ValueError("Decoded packet must be a JSON object")

    if "type" not in packet or "payload" not in packet:
        raise ValueError("Packet missing required fields: 'type' and 'payload'")

    if not isinstance(packet["type"], str) or not packet["type"]:
        raise ValueError("Packet 'type' must be a non-empty string")
    if not isinstance(packet["payload"], dict):
        raise ValueError("Packet 'payload' must be a JSON object")

    return packet


def is_heartbeat(packet_dict: Dict[str, Any]) -> bool:
    """Return True if the packet is a heartbeat (ping or pong)."""

    return packet_dict.get("type") in {HEARTBEAT_PING, HEARTBEAT_PONG}
