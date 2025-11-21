# game/network/packets.py
"""JSON-based packet helpers for the real-time multiplayer game network layer."""

from __future__ import annotations

import json
from typing import Any, Dict

# ------------------------------------------------------------
# PACKET TYPES
# ------------------------------------------------------------

# Connection events
PLAYER_CONNECT = "PLAYER_CONNECT"
PLAYER_DISCONNECT = "PLAYER_DISCONNECT"

# Movement and navigation
PLAYER_MOVE = "PLAYER_MOVE"
MOVE_REJECT = "MOVE_REJECT"
SECTOR_UPDATE = "SECTOR_UPDATE"

# Communication
CHAT_MESSAGE = "CHAT_MESSAGE"

# Heartbeat
HEARTBEAT_PING = "HEARTBEAT_PING"
HEARTBEAT_PONG = "HEARTBEAT_PONG"

# Port trading
PORT_TRADE = "PORT_TRADE"
TRADE_RESULT = "TRADE_RESULT"

# Scanning
SCAN_REQUEST = "SCAN_REQUEST"
SCAN_RESULT = "SCAN_RESULT"

# Stardock docking
DOCK_REQUEST = "DOCK_REQUEST"
DOCK_RESULT = "DOCK_RESULT"
DOCK_ACTION = "DOCK_ACTION"

# ------------------------------------------------------------
# ENCODING / DECODING
# ------------------------------------------------------------

def encode_packet(packet_type: str, payload: Dict[str, Any]) -> str:
    """
    Serialize a packet dictionary to a compact JSON string.
    
    Args:
        packet_type: Type identifier for the packet
        payload: Data payload dictionary
        
    Returns:
        JSON string representation of the packet
        
    Raises:
        ValueError: If packet_type or payload are invalid
    """
    if not isinstance(packet_type, str) or not packet_type:
        raise ValueError("packet_type must be a non-empty string")
    if payload is None or not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    packet = {"type": packet_type, "payload": payload}
    return json.dumps(packet, separators=(",", ":"), ensure_ascii=False)


def decode_packet(raw_json: str) -> Dict[str, Any]:
    """
    Parse a JSON string into a packet dictionary.
    
    Args:
        raw_json: JSON string to decode
        
    Returns:
        Decoded packet dictionary with 'type' and 'payload' keys
        
    Raises:
        ValueError: If JSON is invalid or packet structure is malformed
    """
    try:
        packet = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON packet") from exc

    if not isinstance(packet, dict):
        raise ValueError("Packet must be a JSON object")

    packet_type = packet.get("type")
    payload = packet.get("payload")

    if not isinstance(packet_type, str):
        raise ValueError("Packet missing valid 'type' field")
    if payload is None or not isinstance(payload, dict):
        raise ValueError("Packet missing valid 'payload' field")

    return packet


def is_heartbeat(packet_dict: Dict[str, Any]) -> bool:
    """
    Return True if the packet is a heartbeat ping/pong.
    
    Args:
        packet_dict: Decoded packet dictionary
        
    Returns:
        True if packet is a heartbeat type
    """
    return packet_dict.get("type") in {HEARTBEAT_PING, HEARTBEAT_PONG}


# ------------------------------------------------------------
# PACKET TYPE REGISTRY
# ------------------------------------------------------------

# All valid packet types for validation
VALID_PACKET_TYPES = {
    PLAYER_CONNECT,
    PLAYER_DISCONNECT,
    PLAYER_MOVE,
    MOVE_REJECT,
    SECTOR_UPDATE,
    CHAT_MESSAGE,
    HEARTBEAT_PING,
    HEARTBEAT_PONG,
    PORT_TRADE,
    TRADE_RESULT,
    SCAN_REQUEST,
    SCAN_RESULT,
    DOCK_REQUEST,
    DOCK_RESULT,
    DOCK_ACTION,
}


def is_valid_packet_type(packet_type: str) -> bool:
    """
    Check if a packet type is valid.
    
    Args:
        packet_type: Packet type string to validate
        
    Returns:
        True if packet type is recognized
    """
    return packet_type in VALID_PACKET_TYPES