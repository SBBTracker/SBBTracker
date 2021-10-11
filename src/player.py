from dataclasses import dataclass


@dataclass
class Card:
    name: str
    attack: int
    health: int
    is_golden: bool
    slot: int


empty_card = Card("empty", 0, 0, False, 1)


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

    def get_minion(self, index: int):
        return self.minions.get(index, empty_card)

    def get_treasure(self, index: int):
        return self.treasures.get(index, empty_card.name)
