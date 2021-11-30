from collections import defaultdict

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Qt5Agg")
from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator

matches_per_hero = "Matches per Hero"
mmr_change = "MMR Graph"


class LivePlayerStates:
    def __init__(self):
        self.ids_to_health = defaultdict(dict)
        self.ids_to_xp = defaultdict(dict)
        self.ids_to_fractional_xp = defaultdict(dict)
        self.ids_to_heroes = {}

    def update_player(self, playerid, round_number, health, xp, hero):
        self.ids_to_health[playerid][round_number] = health
        self.ids_to_xp[playerid][round_number] = xp
        self.ids_to_fractional_xp[playerid][round_number] = float(f"{xp[0]}.{int(xp[2]) * 333333333}")
        self.ids_to_heroes[playerid] = hero

    def get_ids(self):
        return self.ids_to_heroes.keys()

    def get_hero(self, player_id):
        return self.ids_to_heroes[player_id]

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


def live_health_graph(states: LivePlayerStates, ax):
    # fig, ax = plt.subplots()
    last_values = []
    # plt.axhline(color='w', linewidth=2.0)
    for player in states.get_ids():
        healths = states.get_healths(player)
        x = list(healths.keys())
        y = list(healths.values())

        last_health = y[-1]
        opacity = 1 if last_health > 0 else .2
        ax.plot(x, y, label=states.get_hero(player), alpha=opacity)
        last_values.append((x[-1], y[-1]))
        ax.annotate(y[-1], (x[-1], y[-1]))
    ax.legend()
    ax.set_xlabel("Turn")
    ax.set_ylabel("Health")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    # fig.set_size_inches(13.5, 18)
    handles, labels = ax.get_legend_handles_labels()
    healths = [health for (_, health) in last_values]
    # sort both labels and handles by labels
    _, labels, handles = zip(*sorted(zip(healths, labels, handles), key=lambda t: t[0], reverse=True))
    ax.legend(handles, labels)
    return plt.gcf()


def xp_graph(states: LivePlayerStates, ax):
    # fig, ax = plt.subplots()
    last_values = []
    # plt.axhline(color='w', linewidth=2.0)
    for player in states.get_ids():
        xps = states.get_fractional_xps(player)
        display_xps = list(states.get_xps(player).values())
        x = list(xps.keys())[0:13]  # filtering only the fist 13 rounds because nothing beyond 6.0 matters
        y = list(xps.values())[0:13]

        ax.plot(x, y, label=states.get_hero(player))
        last_values.append((x[-1], y[-1]))
        ax.annotate(float(display_xps[-1]), (x[-1], y[-1]))
    ax.legend()
    ax.set_xlabel("Turn")
    ax.set_ylabel("XP")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    handles, labels = ax.get_legend_handles_labels()
    experiences = [health for (_, health) in last_values]
    # sort both labels and handles by labels
    _, labels, handles = zip(*sorted(zip(experiences, labels, handles), key=lambda t: t[0], reverse=True))
    ax.legend(handles, labels)
    return plt.gcf()


def hero_freq_graph(df: pd.DataFrame, ax):
    if len(df.index) > 0:
        sorted_df = df.sort_values(by='StartingHero', ascending=True)
        sorted_df = sorted_df[~sorted_df['StartingHero'].str.isspace()]
        heroes = sorted_df["StartingHero"].unique()
        matches = sorted_df.groupby("StartingHero").count()["Placement"].values
        sort_by_wins = matches.argsort()[::-1]
        heroes = heroes[sort_by_wins]
        ax.barh(heroes, matches[sort_by_wins], .8, color='tab:red')
        ind = range(max(matches) + 1)
        ax.invert_yaxis()
        ax.grid(axis='y')
        ax.set_xticks(ind)
        ax.set_title("Matches per Hero")

    return plt.gcf()


def mmr_graph(df: pd.DataFrame, ax):
    mmrs = df["+/-MMR"].tail(20).values.astype(int)
    data = np.cumsum(mmrs)
    timeseries = range(1, len(data) + 1)
    plt.axhline(y=0, color='w', linewidth=2.0)
    ax.plot(timeseries, data, linewidth=3.0)
    ax.set_ylabel("Cumulative MMR")
    ax.set_xlabel("Games")
    ax.set_title("Cumulative MMR over last 20 games")
    ax.set_xticks(range(1, 21))

    return plt.gcf()


def stats_graph(df: pd.DataFrame, graph_type: str, ax):
    if graph_type == mmr_change:
        return mmr_graph(df, ax)
    elif graph_type == matches_per_hero:
        return hero_freq_graph(df, ax)
