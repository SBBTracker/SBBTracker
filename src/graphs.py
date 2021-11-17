import matplotlib
import pandas as pd

matplotlib.use("Qt5Agg")
from matplotlib import pyplot as plt
from matplotlib.ticker import MaxNLocator

matches_per_hero = "Matches per Hero"
mmr_change = "MMR Graph"


def delete_fig_agg(fig_agg):
    fig_agg.get_tk_widget().forget()
    plt.close('all')


def make_health_graph(names_to_health: dict, ids_to_heroes: dict, ax):
    # fig, ax = plt.subplots()
    last_values = []
    # plt.axhline(color='w', linewidth=2.0)
    for player in names_to_health.keys():
        x = []
        y = []
        for round_num in names_to_health[player]:
            x.append(round_num)
            y.append(names_to_health[player][round_num])
        ax.plot(x, y, label=ids_to_heroes[player])
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


def make_hero_freq_graph(df: pd.DataFrame, ax):
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


def make_mmr_graph(df: pd.DataFrame, ax):
    data = df["+/-MMR"].tail(20).values
    timeseries = range(len(data))
    plt.axhline(y=0, color='w', linewidth=2.0)
    ax.plot(timeseries, data, linewidth=3.0)
    ax.set_ylabel("Change in MMR")
    ax.set_title("Last 20 MMR Changes")
    ax.set_xticks(range(1, 21))

    return plt.gcf()


def make_stats_graph(df: pd.DataFrame, graph_type: str, ax):
    if graph_type == mmr_change:
        return make_mmr_graph(df, ax)
    elif graph_type == matches_per_hero:
        return make_hero_freq_graph(df, ax)
