import os.path
from os.path import expanduser
from pathlib import Path, WindowsPath

import PySimpleGUI
import pandas as pd

from src import asset_utils

statsfile = WindowsPath(expanduser('~/Documents')).joinpath("SBBTracker/stats.csv")

headings = ["Hero", "# Matches", "Avg Place", "Top 4", "Wins"]


def update_window(window: PySimpleGUI.Window, hero: str, place: str):
    window.extend_layout(window["-Hero-"], [[PySimpleGUI.T(hero)]])
    window.extend_layout(window["-Placement-"], [[PySimpleGUI.T(place)]])


def generate_stats(window: PySimpleGUI.Window, df):
    df["Placement"] = pd.to_numeric(df["Placement"])
    heroes = sorted(set(df['Hero']))

    data = []
    for hero in heroes:
        bool_df = df['Hero'] == hero
        total_matches = sum(bool_df)
        avg = round(df.loc[bool_df, 'Placement'].sum() / total_matches, 2)
        total_top4 = len(df.loc[bool_df & (df['Placement'] <= 4), 'Placement'])
        total_wins = len(df.loc[bool_df & (df['Placement'] <= 1), 'Placement'])
        data.append([hero, str(total_matches), str(avg), str(total_top4), str(total_wins)])

    table = window["-HeroStats-"]
    table.update(values=data)

class PlayerStats:

    def __init__(self, window: PySimpleGUI.Window):
        self.window = window
        if os.path.exists(statsfile):
            self.df = pd.read_csv(str(statsfile))
            for row in self.df.itertuples():
                update_window(self.window, row.Hero, row.Placement)
            generate_stats(self.window, self.df)
        else:
            self.df = pd.DataFrame(columns=['Hero', 'Placement'])

    def export(self, filepath: Path):
        try:
            if not filepath.parent.exists():
                os.makedirs(filepath.parent)
            self.df.to_csv(str(filepath), index=False)
        except Exception as e:
            print(e)

    def save(self):
        self.export(statsfile)

    def update_stats(self, hero: str, placement: str):
        self.df = self.df.append({"Hero": hero, "Placement": placement}, ignore_index=True)
        update_window(self.window, hero, placement)
