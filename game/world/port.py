# game/world/port.py
"""
Trading port system for TradeWars 2025.

Ports are commercial stations that buy and sell commodities:
- Each port has a type (1-3) determining what it buys/sells
- Dynamic pricing based on commodity levels
- Three commodities: fuel, ore, equipment
"""

from __future__ import annotations
from dataclasses import dataclass, field
import random
from typing import Dict, Any

# ------------------------------------------------------------
# Commodity Definitions
# ------------------------------------------------------------

COMMODITIES = ["fuel", "ore", "equipment"]

BASE_PRICES = {
    "fuel": 10,
    "ore": 25,
    "equipment": 50,
}

# Port types determine buy/sell behavior
# "buy" means port BUYS from players (players SELL to port)
# "sell" means port SELLS to players (players BUY from port)
PORT_TYPES = {
    1: {"fuel": "buy",  "ore": "sell", "equipment": "sell"},  # Fuel refinery
    2: {"fuel": "sell", "ore": "buy",  "equipment": "sell"},  # Mining station
    3: {"fuel": "sell", "ore": "sell", "equipment": "buy"},   # Tech outpost
}

# Random name tables for procedural generation
PORT_PREFIXES = [
    "Rigel", "Sigma", "Omega", "Alpha", "Beta", "Tau",
    "Nova", "Epsilon", "Orion", "Kappa", "Gamma",
    "Vega", "Zeta", "Helios", "Astra", "Cygnus",
    "Zenith", "Prax", "Lumen", "Draco", "Solara"
]

PORT_SUFFIXES = [
    "Station", "Tradeport", "Depot", "Exchange",
    "Bazaar", "Harbor", "Outpost", "Citadel",
    "Hub", "Market", "Annex", "Platform"
]


def random_port_name() -> str:
    """
    Generate a random port name.
    
    Returns:
        Random port name combining prefix and suffix
    """
    return f"{random.choice(PORT_PREFIXES)} {random.choice(PORT_SUFFIXES)}"


# ------------------------------------------------------------
# Port Object
# ------------------------------------------------------------

@dataclass
class Port:
    """
    Full-featured TradeWars-style trading port.
    
    Attributes:
        name: Port display name
        type_id: Port type (1-3) determining trade behavior
        commodity_levels: Stock levels for each commodity (0-100)
        prices: Current prices for each commodity
        modes: Buy/sell modes for each commodity (derived from type_id)
    """

    name: str = None
    type_id: int = None
    commodity_levels: Dict[str, int] = field(default_factory=lambda: {
        c: random.randint(20, 80) for c in COMMODITIES
    })
    prices: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize port after dataclass construction."""
        # Generate random name if not provided
        if self.name is None:
            self.name = random_port_name()

        # Assign random type if not provided
        if self.type_id is None:
            self.type_id = random.choice(list(PORT_TYPES.keys()))

        # Validate type_id
        if self.type_id not in PORT_TYPES:
            raise ValueError(f"Invalid port type_id: {self.type_id}. Must be 1, 2, or 3.")

        # Set buy/sell modes based on type
        self.modes = PORT_TYPES[self.type_id]

        # Generate initial prices if missing
        if not self.prices:
            self.update_prices()

        # Validate commodity levels
        for commodity in COMMODITIES:
            if commodity not in self.commodity_levels:
                self.commodity_levels[commodity] = random.randint(20, 80)
            else:
                # Clamp to valid range
                self.commodity_levels[commodity] = max(0, min(100, self.commodity_levels[commodity]))

    # --------------------------------------------------------
    # Price Logic
    # --------------------------------------------------------

    def update_prices(self) -> None:
        """
        Calculate current commodity prices based on stock levels.
        
        Port pricing follows supply/demand:
        - Ports that BUY: Higher stock = lower buy price
        - Ports that SELL: Lower stock = higher sell price
        """
        for c in COMMODITIES:
            base = BASE_PRICES[c]
            level = self.commodity_levels.get(c, 50)

            # Dynamic pricing based on mode
            if self.modes[c] == "sell":
                # Port sells to players: low stock = expensive
                factor = 0.6 + (100 - level) / 150.0
            else:  # "buy"
                # Port buys from players: high stock = cheap
                factor = 1.0 + level / 150.0

            # Calculate price with minimum floor
            self.prices[c] = max(5, int(base * factor))

    def adjust_commodity_level(self, commodity: str, amount: int) -> None:
        """
        Adjust commodity stock level (for future dynamic economy).
        
        Args:
            commodity: Commodity name
            amount: Amount to adjust (positive or negative)
        """
        if commodity not in COMMODITIES:
            raise ValueError(f"Unknown commodity: {commodity}")
        
        current = self.commodity_levels.get(commodity, 50)
        new_level = max(0, min(100, current + amount))
        self.commodity_levels[commodity] = new_level
        
        # Recalculate prices after level change
        self.update_prices()

    def get_commodity_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed info about all commodities at this port.
        
        Returns:
            Dictionary with commodity details including mode, level, price
        """
        return {
            commodity: {
                "mode": self.modes[commodity],
                "level": self.commodity_levels[commodity],
                "price": self.prices[commodity],
                "base_price": BASE_PRICES[commodity],
            }
            for commodity in COMMODITIES
        }

    # --------------------------------------------------------
    # Save / Load
    # --------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize port to dictionary for saving.
        
        Returns:
            Dictionary representation of port state
        """
        return {
            "name": self.name,
            "type_id": self.type_id,
            "commodity_levels": self.commodity_levels,
            "prices": self.prices,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Port":
        """
        Restore port from saved data with backward compatibility.
        
        Args:
            data: Saved port data dictionary
            
        Returns:
            Restored Port instance
            
        Raises:
            ValueError: If data is invalid
        """
        # Validate input
        if not isinstance(data, dict):
            raise ValueError("Port data must be a dictionary")

        # Extract basic fields with defaults
        name = data.get("name", None)
        type_id = data.get("type_id", None)

        # Validate type_id if provided
        if type_id is not None and type_id not in PORT_TYPES:
            print(f"[WARNING] Invalid port type_id {type_id}, assigning random type")
            type_id = None

        # Create port instance (will auto-generate missing fields)
        port = Port(
            name=name,
            type_id=type_id,
        )

        # Restore commodity levels with validation
        if "commodity_levels" in data and isinstance(data["commodity_levels"], dict):
            port.commodity_levels = {}
            for commodity in COMMODITIES:
                if commodity in data["commodity_levels"]:
                    # Clamp to valid range
                    level = data["commodity_levels"][commodity]
                    port.commodity_levels[commodity] = max(0, min(100, int(level)))
                else:
                    port.commodity_levels[commodity] = random.randint(20, 80)
        else:
            # Generate default levels
            port.commodity_levels = {c: random.randint(20, 80) for c in COMMODITIES}

        # Restore prices or recalculate
        if "prices" in data and isinstance(data["prices"], dict):
            port.prices = {}
            for commodity in COMMODITIES:
                if commodity in data["prices"]:
                    port.prices[commodity] = max(1, int(data["prices"][commodity]))
                else:
                    # Calculate missing price
                    port.prices[commodity] = BASE_PRICES[commodity]
        else:
            # Recalculate all prices from levels
            port.update_prices()

        # Ensure modes are set
        if not hasattr(port, "modes") or not port.modes:
            port.modes = PORT_TYPES[port.type_id]

        # Ensure name exists
        if port.name is None:
            port.name = random_port_name()

        return port

    # --------------------------------------------------------
    # Display / Debug
    # --------------------------------------------------------

    def __str__(self) -> str:
        """String representation for debugging."""
        mode_str = ", ".join(f"{c}:{self.modes[c]}" for c in COMMODITIES)
        return f"Port({self.name}, Type {self.type_id}, {mode_str})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"Port(name='{self.name}', type_id={self.type_id}, "
            f"levels={self.commodity_levels}, prices={self.prices})"
        )

    def get_trade_summary(self) -> str:
        """
        Get human-readable trading summary.
        
        Returns:
            Multi-line string describing port trading options
        """
        lines = [
            f"=== {self.name} (Type {self.type_id}) ===",
            "",
        ]
        
        for commodity in COMMODITIES:
            mode = self.modes[commodity]
            price = self.prices[commodity]
            level = self.commodity_levels[commodity]
            
            if mode == "sell":
                action = "SELLING"
            else:
                action = "BUYING"
            
            lines.append(
                f"{commodity.capitalize():12} | {action:7} | "
                f"{price:4} cr | Stock: {level:3}%"
            )
        
        return "\n".join(lines)