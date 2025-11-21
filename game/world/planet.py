class Planet:
    """Placeholder planet object for MVP gameplay."""
    def __init__(self, sector_id: int):
        self.sector_id = sector_id
        self.name = f"Planet-{sector_id}"

    def to_dict(self):
        return {
            "sector_id": self.sector_id,
            "name": self.name,
        }

    @staticmethod
    def from_dict(data):
        p = Planet(data["sector_id"])
        p.name = data.get("name", p.name)
        return p
