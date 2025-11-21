# galaxy.py
import random
from game.world.port import Port
from game.world.planet import Planet



class Sector:
    """
    A sector is a node in the galaxy map.
    Each sector has:
    - id
    - name
    - neighbors (warp lanes)
    - optional port
    - optional planet
    - type (STARDOCK, FEDSPACE, PIRATE, DEADEND, NORMAL)
    - has_pirates flag
    """

    def __init__(self, sid):
        self.id = sid
        self.name = f"Sector {sid}"
        self.neighbors = set()
        self.port = None
        self.planet = None
        self.type = "NORMAL"   # always defined
        self.has_pirates = False


class Galaxy:
    """
    Generates a TradeWars-style galaxy.
    """

    START_SECTOR = 1   # ← ADD THIS LINE

    def __init__(self, num_sectors=100):
        self.num_sectors = num_sectors
        self.sectors = {}

        self._create_sectors()
        self._generate_base_ring()
        self._add_random_links()
        self._assign_special_sectors()
        self._generate_ports_and_planets()

    # ----------------------------------------------------------
    # Creation & Base Structure
    # ----------------------------------------------------------

    def _create_sectors(self):
        for sid in range(1, self.num_sectors + 1):
            self.sectors[sid] = Sector(sid)

    def _generate_base_ring(self):
        """Create a circular backbone ensuring the galaxy is connected."""
        for sid in range(1, self.num_sectors + 1):
            next_sid = sid + 1 if sid < self.num_sectors else 1
            self.sectors[sid].neighbors.add(next_sid)
            self.sectors[next_sid].neighbors.add(sid)

    def _add_random_links(self):
        """Add random connections for better navigation variety."""
        extra_links = max(3, self.num_sectors // 6)

        for _ in range(extra_links):
            a = random.randint(1, self.num_sectors)
            b = random.randint(1, self.num_sectors)
            if a != b:
                self.sectors[a].neighbors.add(b)
                self.sectors[b].neighbors.add(a)

    # ----------------------------------------------------------
    # Special Sector Assignment
    # ----------------------------------------------------------

    def _assign_special_sectors(self):
        """
        TW-style logical layout:
        - Sectors 1–5 = FedSpace (safe zone)
        - Sector 3 = Stardock
        - Random Pirate sectors
        - Random Dead-end sectors
        """

        # FEDSPACE: Sectors 1 through 5
        for sid in range(1, min(6, self.num_sectors + 1)):
            self.sectors[sid].type = "FEDSPACE"

        # STARDOCK placed at sector 3 (classic TW location)
        if 3 <= self.num_sectors:
            self.sectors[3].type = "STARDOCK"

        # PIRATE sectors: about 10% of map, avoid FedSpace
        pirate_count = max(2, self.num_sectors // 12)
        pirate_candidates = [
            sid for sid in self.sectors.keys()
            if self.sectors[sid].type == "NORMAL"
        ]
        random.shuffle(pirate_candidates)
        for sid in pirate_candidates[:pirate_count]:
            sec = self.sectors[sid]
            sec.type = "PIRATE"
            sec.has_pirates = True

        # DEADEND sectors: sectors with only 1 connection
        for sid, sec in self.sectors.items():
            if len(sec.neighbors) == 1 and sec.type == "NORMAL":
                sec.type = "DEADEND"

    # ----------------------------------------------------------
    # Ports & Planets
    # ----------------------------------------------------------

    def _generate_ports_and_planets(self):
        """
        Assign ports and planets based on probabilities.
        Stardock never gets a port.
        """
        for sid, sector in self.sectors.items():

            # Skip Stardock (you can also skip FedSpace if you want)
            if sector.type == "STARDOCK":
                continue

            # 40% chance sector has a port
            if random.random() < 0.4:
                sector.port = Port()

            # 20% chance sector has a planet
            if random.random() < 0.2:
                sector.planet = Planet(sector.id)

    # ----------------------------------------------------------
    # Save/Load Support
    # ----------------------------------------------------------

    def to_dict(self):
        return {
            "num_sectors": self.num_sectors,
            "sectors": {
                sid: {
                    "id": sec.id,
                    "neighbors": list(sec.neighbors),
                    "type": sec.type,
                    "has_pirates": sec.has_pirates,
                    "port": sec.port.to_dict() if sec.port else None,
                    "planet": sec.planet.to_dict() if sec.planet else None,
                }
                for sid, sec in self.sectors.items()
            }
        }

    # ----------------------------------------------------------
    # Sector Lookup Helper (TW25Game depends on this)
    # ----------------------------------------------------------
    def get_sector(self, sid):
        return self.sectors.get(sid)
       
    # ----------------------------------------------------------
    # Multiplayer helpers
    # ----------------------------------------------------------

    def sector_exists(self, sid: int) -> bool:
        """Return True if a sector ID exists in the galaxy."""
        return sid in self.sectors

    def is_adjacent(self, current: int, requested: int) -> bool:
        """Validate a legal warp lane between sectors."""
        if current not in self.sectors:
            return False
        return requested in self.sectors[current].neighbors

    def serialize_sector(self, sid: int) -> dict:
        """Return a dictionary representation of a sector for network transmission."""
        sec = self.sectors[sid]
        return {
            "id": sec.id,
            "neighbors": list(sec.neighbors),
            "type": sec.type,
            "has_pirates": sec.has_pirates,
            "port": sec.port.to_dict() if sec.port else None,
            "planet": sec.planet.to_dict() if sec.planet else None,
        }


    # ----------------------------------------------------------
    # Shortest Distance Between Two Sectors (Breadth-First Search)
    # ----------------------------------------------------------
    def shortest_distance(self, start, goal):
        """
        Returns the shortest number of hops between two sectors.
        Uses BFS since the map is an unweighted graph.
        """
        if start == goal:
            return 0

        visited = set()
        queue = [(start, 0)]  # (sector, distance)

        while queue:
            current, dist = queue.pop(0)

            if current == goal:
                return dist

            visited.add(current)

            for neighbor in self.sectors[current].neighbors:
                if neighbor not in visited:
                    queue.append((neighbor, dist + 1))

        return None

    # ----------------------------------------------------------
    # Shortest Path Between Two Sectors (BFS)
    # ----------------------------------------------------------
    def shortest_path(self, start, goal):
        """
        Returns the actual shortest path between two sectors as a list.
        Example: [1, 5, 9, 12]
        """
        if start == goal:
            return [start]

        from collections import deque

        visited = set()
        queue = deque([[start]])  # each item is a path list

        while queue:
            path = queue.popleft()
            node = path[-1]

            if node == goal:
                return path

            if node in visited:
                continue

            visited.add(node)

            for neighbor in self.sectors[node].neighbors:
                if neighbor not in visited:
                    new_path = list(path)
                    new_path.append(neighbor)
                    queue.append(new_path)

        return None

    @staticmethod
    def from_dict(data):
        g = Galaxy(data["num_sectors"])

        # overwrite generated map with saved map data
        for sid, info in data["sectors"].items():
            sid = int(sid)
            sec = g.sectors[sid]

            sec.neighbors = set(info["neighbors"])
            sec.type = info["type"]
            sec.has_pirates = info.get("has_pirates", sec.type == "PIRATE")

            if info["port"]:
                sec.port = Port.from_dict(info["port"])

            if info["planet"]:
                sec.planet = Planet.from_dict(info["planet"])

        return g
