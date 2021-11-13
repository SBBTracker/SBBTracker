from enum import Enum


def get_tab_key(index: int):
    return f"-tab{index}-"


def get_graph_key(index: int):
    return f"-graph{index}-"


def get_player_round_key(index: int):
    return f"-round{index}-"


stats_per_page = 37


class Keys(Enum):
    StartingHeroStats = "-StartingHeroStats-"
    EndingHeroStats = "-EndingHeroStats-"
    MatchStats = "-MatchStats-"
    GameStatus = "-GameStatus-"
    HealthGraph = "-HealthGraph-"
    StatsPageNum = "-StatsPageNum-"
    ReattachButton = "-Reattach-"
    CustomDateButton = "-CustomDate-"
    FilterableDates = "-FilterableDates-"
    FilterDateButton = "-FilterDateButton-"
    StatGraphs = "-StatGraphs-"
