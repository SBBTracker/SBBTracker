import json
from collections import defaultdict

import matplotlib
import numpy as np
import pandas as pd

from sbbtracker.languages import tr

matplotlib.use("Qt5Agg")
from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator

matches_per_hero = tr("Matches per Hero")
mmr_change = tr("MMR Graph")
color_palettes = {
    'paired':  ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00'],
    'set':     ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf'],
    'vibrant': ['#0077BB', '#33BBEE', '#009988', '#EE7733', '#CC3311', '#EE3377', '#BBBBBB', '#000000'],
    'scarbo':  ['#000000', '#990000', '#0000CC', '#FF0000', '#4747eb', '#e08585', '#bdbddb', '#FFFFFF'],
}


class LivePlayerStates:
    def __init__(self):
        self.ids_to_health = defaultdict(dict)
        self.ids_to_xp = defaultdict(dict)
        self.ids_to_fractional_xp = defaultdict(dict)
        self.ids_to_heroes = defaultdict(list)
        self.ids_to_hero_ids = defaultdict(list)

    def update_player(self, playerid, round_number, health, xp, hero, hero_id):
        self.ids_to_health[playerid][round_number] = health
        self.ids_to_xp[playerid][round_number] = xp
        self.ids_to_fractional_xp[playerid][round_number] = float(f"{xp[0]}.{int(xp[2]) * 333333333}")
        self.ids_to_heroes[playerid].append(hero)
        self.ids_to_hero_ids[playerid].append(hero_id)

    def get_ids(self):
        return list(self.ids_to_heroes.keys())

    def get_hero(self, player_id):
        return self.ids_to_heroes[player_id][-1]

    def get_healths(self, player_id):
        return self.ids_to_health[player_id]

    def get_xps(self, player_id):
        return self.ids_to_xp[player_id]

    def get_fractional_xps(self, player_id):
        return self.ids_to_fractional_xp[player_id]

    def clear(self):
        self.ids_to_health.clear()
        self.ids_to_xp.clear()
        self.ids_to_fractional_xp.clear()
        self.ids_to_heroes.clear()
        self.ids_to_hero_ids.clear()

    def json_friendly(self):
        players = [
            {
                "player-id": player_id,
                "heroes": self.ids_to_hero_ids[player_id],
                "healths": self.ids_to_health[player_id],
                "xps": self.ids_to_xp[player_id]
            } for player_id in self.ids_to_heroes.keys()
        ]
        return players

    def to_json(self):
        return json.dumps(self.json_friendly(), separators=(',', ':'))

# live graphs


def live_health_graph(states: LivePlayerStates, ax, palette):
    players = states.get_ids()
    last_values = [list(states.get_healths(player).values())[-1] for player in players]
    colors = color_palettes[palette]

    idx = np.argsort(np.array(last_values))[::-1]
    players = np.array(players)[idx]

    for index, player in enumerate(players):
        healths = states.get_healths(player)
        x = list(healths.keys())
        y = list(healths.values())

        last_health = y[-1]
        opacity = 1 if last_health > 0 else .2
        ax.plot(x, y, label=states.get_hero(player), alpha=opacity, color=colors[index], linewidth=3.0)
        ax.annotate(y[-1], (x[-1], y[-1]))
    ax.legend(framealpha=1, labelcolor=colors)
    ax.set_xlabel("Turn")
    ax.set_ylabel("Health")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    return plt.gcf()


def xp_graph(states: LivePlayerStates, ax, palette):
    players = states.get_ids()
    last_values = [list(states.get_fractional_xps(player).values())[-1] for player in players]
    colors = color_palettes[palette]

    idx = np.argsort(np.array(last_values))[::-1]
    players = np.array(players)[idx]

    for index, player in enumerate(players):
        xps = states.get_fractional_xps(player)
        display_xps = list(states.get_xps(player).values())
        x = list(xps.keys())[0:13]  # filtering only the fist 13 rounds because nothing beyond 6.0 matters
        y = list(xps.values())[0:13]

        ax.plot(x, y, label=states.get_hero(player), color=colors[index], linewidth=3.0)
        ax.annotate(float(display_xps[-1]), (x[-1], y[-1]))
    ax.legend(framealpha=1, labelcolor=colors)
    ax.set_xlabel("Turn")
    ax.set_ylabel("XP")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    return plt.gcf()

# static graphs


def hero_freq_graph(df: pd.DataFrame, ax):
    if len(df.index) > 0:
        sorted_df = df.sort_values(by='StartingHero', ascending=True)
        sorted_df = sorted_df[~sorted_df['StartingHero'].str.isspace()]
        heroes = sorted_df["StartingHero"].unique()
        matches = sorted_df.groupby("StartingHero").count()["Placement"].values
        sort_by_wins = matches.argsort()[::-1]
        heroes = heroes[sort_by_wins]
        if len(matches) > 0:
            # catches old data
            ax.barh(heroes, matches[sort_by_wins], .8, color='tab:red')
            ind = range(max(matches) + 1)
            ax.invert_yaxis()
            ax.grid(axis='y')
            # ax.set_xticks(ind)
            ax.set_title("Matches per Hero")

    return plt.gcf()


def mmr_graph(df: pd.DataFrame, ax, mmr_range):
    mmrs = df["+/-MMR"].tail(mmr_range).values.astype(int)
    data = np.cumsum(mmrs)
    timeseries = range(1, len(data) + 1)
    plt.axhline(y=0, color='w', linewidth=2.0)
    ax.plot(timeseries, data, linewidth=3.0)
    ax.set_ylabel(tr("Cumulative MMR"))
    ax.set_xlabel(tr("Games"))
    ax.set_title(tr("Cumulative MMR over last {0} games").format(mmr_range))
    # ax.set_xticks(range(1, 21))

    return plt.gcf()


def stats_graph(df: pd.DataFrame, graph_type: str, ax, mmr_range=25):
    if graph_type == mmr_change:
        return mmr_graph(df, ax, mmr_range)
    elif graph_type == matches_per_hero:
        return hero_freq_graph(df, ax)
