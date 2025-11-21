# game/world/port.py

from __future__ import annotations
from typing import Dict


class Port:
    """
    Simple TradeWars-style port for MVP trading.
    - One set of goods with fixed prices (for now).
    - No stock limits yet – just basic buy/sell.
    """

    def __init__(self) -> None:
        # price per unit
        self.prices: Dict[str, int] = {
            "fuel": 10,
            "ore": 25,
            "equipment": 50,
        }

    def to_dict(self) -> Dict:
        return {
            "prices": self.prices,
        }

    @staticmethod
    def from_dict(data: Dict) -> "Port":
        p = Port()
        p.prices = data.get("prices", p.prices)
        return p
