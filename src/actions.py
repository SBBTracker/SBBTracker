from dataclasses import dataclass


@dataclass
class Action:
    task: str


class CreateCard(Action):
    player_id: str
    card_name: str
    card_attack: str
    card_health: str
    is_golden: str
    slot: str
    zone: str
    content_id: str


class AddPlayer(Action):
    display_name: str
    hero_name: str
    hero_id: str
    health: int
    player_id: str


class EnterBrawl(Action):
    player1: dict
    player2: dict


class EndRoundGather(Action):
    pass


class EnterShopPhase(Action):
    round: int

