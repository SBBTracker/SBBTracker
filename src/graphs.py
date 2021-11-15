import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator

matches_per_hero = "Matches per Hero"
mmr_change = "MMR Graph"


def draw_matplotlib_figure(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw_idle()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg


def delete_fig_agg(fig_agg):
    fig_agg.get_tk_widget().forget()
    plt.close('all')


def make_health_graph(names_to_health: dict, ids_to_heroes: dict):
    fig, ax = plt.subplots()
    last_values = []
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
    plt.axhline(y=0, color='w', linewidth=2.0)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.set_size_inches(13.5, 18)
    handles, labels = ax.get_legend_handles_labels()
    healths = [health for (_, health) in last_values]
    # sort both labels and handles by labels
    _, labels, handles = zip(*sorted(zip(healths, labels, handles), key=lambda t: t[0], reverse=True))
    ax.legend(handles, labels)
    return plt.gcf()


def make_hero_freq_graph(df: pd.DataFrame):
    if len(df.index) > 0:
        fig, ax = plt.subplots()
        fig.set_size_inches(13.5, 18)
        sorted_df = df.sort_values(by='StartingHero', ascending=True)
        sorted_df = sorted_df[~sorted_df['StartingHero'].str.isspace()]
        heroes = sorted_df["StartingHero"].unique()
        matches = sorted_df.groupby("StartingHero").count()["Placement"].values
        firsts = sorted_df.groupby("StartingHero").apply(lambda x: sum(x.Placement <= 1)).values
        top4s = sorted_df.groupby("StartingHero").apply(lambda x: sum(x.Placement <= 4)) - firsts
        top8s = sorted_df.groupby("StartingHero").apply(lambda x: sum(x.Placement > 4)).values
        sort_by_wins = matches.argsort()[::-1]
        heroes = heroes[sort_by_wins]
        firsts = firsts[sort_by_wins]
        top4s = top4s[sort_by_wins]
        top8s = top8s[sort_by_wins]
        ax.barh(heroes, matches[sort_by_wins], .8, color='tab:red', label="Top 8s")
        # ax.barh(heroes, top8s, .8, color='tab:red', label="Top 8s")
        # ax.barh(heroes, top4s, .8, left=top8s, color='tab:green', label="Top 4s")
        # ax.barh(heroes, firsts, .8, left=(top4s + top8s), color='gold', label="Wins")
        ind = range(max(matches) + 1)
        ax.invert_yaxis()
        ax.grid(axis='y')
        ax.set_xticks(ind)
        plt.title("Matches per Hero")
    # ax.legend()
    # ax.set_yticklabels(heroes, rotation=90)

    return plt.gcf()


def make_mmr_graph(df: pd.DataFrame):
    fig, ax = plt.subplots()
    fig.set_size_inches(13.5, 18)
    data = df["+/-MMR"].tail(20).values
    timeseries = range(len(data))
    ax.plot(timeseries, data)
    ax.set_ylabel("Change in MMR")
    plt.title("Last 20 MMR Changes")
    plt.xticks(range(1, 21))

    return plt.gcf()


def make_stats_graph(df: pd.DataFrame, graph_type: str):
    if graph_type == mmr_change:
        return make_mmr_graph(df)
    elif graph_type == matches_per_hero:
        return make_hero_freq_graph(df)
