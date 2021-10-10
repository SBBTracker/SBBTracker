from dataclasses import dataclass

@dataclass
class Card:
    name: str
    attack: int
    health: int
    is_golden: bool
    slot: int

@dataclass
class Player:
    name: str
    id: str
    last_seen: int
    hero: str
    treasures: dict[int, str]
    minions: dict[int, Card]
    spell: str
    health: int
    level: int


