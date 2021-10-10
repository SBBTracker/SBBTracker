from dataclasses import dataclass


@dataclass
class Player:
    name: str
    id: str
    last_seen: int
    hero: str
    treasures: list[str]
    minions: dict[str]
    spell: str
