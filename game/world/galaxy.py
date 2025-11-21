# game/world/galaxy.py
"""
Galaxy generation and management for TradeWars 2025.

The galaxy consists of interconnected sectors with various features:
- Warp routes connecting sectors
- Trading ports with commodity markets
- Stardock (Celestial Bazaar) in sector 2
- Future: planets, anomalies, NPCs
"""

import random
from typing import Dict, Optional, Any
from game.world.port import Port


# ============================================================
# SECTOR
# ============================================================

class Sector:
    """
    Represents a single sector in the galaxy.
    
    Attributes:
        id: Unique sector identifier
        neighbors: List of adjacent sector IDs (warp routes)
        port: Trading port instance (if present)
        planet: Planet data (future expansion)
        is_stardock: Whether this sector contains a stardock
    """
    
    def __init__(self, sector_id: int):
        """
        Initialize a new sector.
        
        Args:
            sector_id: Unique identifier for this sector
        """
        self.id = sector_id
        self.neighbors = []
        self.port = None
        self.planet = None
        self.is_stardock = False

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize sector to dictionary for saving.
        
        Returns:
            Dictionary representation of sector state
        """
        return {
            "id": self.id,
            "neighbors": self.neighbors,
            "port": self.port.to_dict() if self.port else None,
            "planet": self.planet,
            "stardock": self.is_stardock,
        }

    @staticmethod
    def from_dict(sec_data: dict, sector_obj: "Sector") -> "Sector":
        """
        Restore a sector object from saved data.
        
        Args:
            sec_data: Saved sector data dictionary
            sector_obj: Sector object to populate
            
        Returns:
            Populated sector object
        """
        # Validate input
        if not isinstance(sec_data, dict):
            raise ValueError("Sector data must be a dictionary")
        
        # Restore neighbors (warp routes)
        if "neighbors" in sec_data:
            if isinstance(sec_data["neighbors"], list):
                sector_obj.neighbors = sec_data["neighbors"]
            else:
                sector_obj.neighbors = []

        # Restore planets (future expansion)
        if "planet" in sec_data:
            sector_obj.planet = sec_data["planet"]

        # Restore ports
        if sec_data.get("port"):
            try:
                sector_obj.port = Port.from_dict(sec_data["port"])
            except Exception as e:
                print(f"[WARNING] Failed to load port in sector {sector_obj.id}: {e}")
                sector_obj.port = None

        # Restore stardock flag - ensure boolean conversion
        sector_obj.is_stardock = bool(sec_data.get("stardock", False))

        return sector_obj


# ============================================================
# GALAXY
# ============================================================

class Galaxy:
    """
    Manages the entire galaxy of interconnected sectors.
    
    Attributes:
        size: Total number of sectors
        sectors: Dictionary mapping sector ID to Sector object
    """
    
    def __init__(self, size: int = 200):
        """
        Initialize a new galaxy or restore from saved data.
        
        Args:
            size: Number of sectors in the galaxy (default: 200)
        """
        self.size = size
        self.sectors: Dict[int, Sector] = {
            i: Sector(i) for i in range(1, size + 1)
        }

        # ALWAYS place stardock in sector 2 BEFORE generating ports
        if 2 in self.sectors:
            self.sectors[2].is_stardock = True
            print(f"[GALAXY] Stardock initialized in sector 2")

        self.generate_warps()
        self.generate_ports()

        # Double-check sector 2 doesn't have a port (stardock exclusive)
        if 2 in self.sectors:
            if self.sectors[2].port is not None:
                print(f"[WARNING] Removing port from stardock sector 2")
                self.sectors[2].port = None

    # ------------------------------------------------------------
    # Warp links generation
    # ------------------------------------------------------------

    def generate_warps(self) -> None:
        """
        Generate warp route connections between sectors.
        
        Each sector gets 2-4 random warp connections to other sectors,
        creating a connected graph for navigation.
        """
        for i in range(1, self.size + 1):
            warp_count = random.randint(2, 4)
            
            # Select random destinations (excluding self)
            possible_destinations = [x for x in range(1, self.size + 1) if x != i]
            choices = random.sample(possible_destinations, min(warp_count, len(possible_destinations)))
            
            self.sectors[i].neighbors = choices

    # ------------------------------------------------------------
    # Port generation
    # ------------------------------------------------------------

    def generate_ports(self) -> None:
        """
        Generate trading ports throughout the galaxy.
        
        Places ports in approximately 20% of sectors (size // 5).
        Sector 2 is excluded as it contains the stardock.
        """
        port_count = max(1, self.size // 5)  # At least 1 port
        
        # Select random sectors for ports (excluding sector 2 - stardock)
        available_sectors = [s for s in range(1, self.size + 1) if s != 2]
        choices = random.sample(available_sectors, min(port_count, len(available_sectors)))

        for sid in choices:
            self.sectors[sid].port = Port()

    # ------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize entire galaxy to dictionary for saving.
        
        Returns:
            Dictionary containing galaxy size and all sector data
        """
        return {
            "size": self.size,
            "sectors": {sid: s.to_dict() for sid, s in self.sectors.items()}
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Galaxy":
        """
        Restore galaxy from saved data.
        
        Args:
            data: Saved galaxy data dictionary
            
        Returns:
            Restored Galaxy instance
        """
        if not isinstance(data, dict):
            raise ValueError("Galaxy data must be a dictionary")
        
        # Backward compatibility — infer size if missing
        if "size" in data:
            size = data["size"]
        else:
            # Infer from sectors
            sectors_data = data.get("sectors", {})
            if sectors_data:
                size = max(int(x) for x in sectors_data.keys())
            else:
                size = 200  # Default fallback

        # Create fresh galaxy structure
        g = Galaxy(size=size)

        # Restore sector data
        sectors_data = data.get("sectors", {})

        for sid, sec_data in sectors_data.items():
            try:
                sid_int = int(sid)
                if sid_int in g.sectors:
                    Sector.from_dict(sec_data, g.sectors[sid_int])
            except (ValueError, TypeError) as e:
                print(f"[WARNING] Failed to load sector {sid}: {e}")
                continue

        return g

    # ------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------

    def sector_exists(self, sid: int) -> bool:
        """
        Check if a sector exists in the galaxy.
        
        Args:
            sid: Sector ID to check
            
        Returns:
            True if sector exists
        """
        return sid in self.sectors

    def is_adjacent(self, src: int, dst: int) -> bool:
        """
        Check if two sectors are connected by a warp route.
        
        Args:
            src: Source sector ID
            dst: Destination sector ID
            
        Returns:
            True if sectors are adjacent (warp connection exists)
        """
        if src not in self.sectors:
            return False
        return dst in self.sectors[src].neighbors

    def get_sector(self, sid: int) -> Optional[Sector]:
        """
        Get sector object by ID.
        
        Args:
            sid: Sector ID
            
        Returns:
            Sector object or None if not found
        """
        return self.sectors.get(sid)

    # ------------------------------------------------------------
    # Client serialization (limited info)
    # ------------------------------------------------------------

    def serialize_sector(self, sid: int) -> Dict[str, Any]:
        """
        Serialize sector data for client transmission.
        
        Only includes information that should be visible to the client,
        hiding internal details like exact port inventory levels.
        
        Args:
            sid: Sector ID to serialize
            
        Returns:
            Dictionary with client-visible sector information
        """
        if sid not in self.sectors:
            return {}

        s = self.sectors[sid]

        return {
            "id": s.id,
            "neighbors": s.neighbors,
            "has_port": s.port is not None,
            "has_planet": s.planet is not None,
            "stardock": s.is_stardock,
            "port_name": s.port.name if s.port else None,
        }

    # ------------------------------------------------------------
    # Statistics and debugging
    # ------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get galaxy statistics for debugging and admin tools.
        
        Returns:
            Dictionary containing galaxy metrics
        """
        port_count = sum(1 for s in self.sectors.values() if s.port is not None)
        stardock_count = sum(1 for s in self.sectors.values() if s.is_stardock)
        planet_count = sum(1 for s in self.sectors.values() if s.planet is not None)
        
        # Calculate average connections
        total_connections = sum(len(s.neighbors) for s in self.sectors.values())
        avg_connections = total_connections / len(self.sectors) if self.sectors else 0

        return {
            "size": self.size,
            "ports": port_count,
            "stardocks": stardock_count,
            "planets": planet_count,
            "avg_warp_routes": round(avg_connections, 2),
        }