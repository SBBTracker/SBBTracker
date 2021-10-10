from dataclasses import dataclass

@dataclass
class Card:
    name: str
    attack: int
    health: int

@dataclass
class Player:
    name: str
    id: str
    last_seen: int
    hero: str
    treasures: list[str]
    minions: dict[Card]
    spell: str
    health: int
    level: int


