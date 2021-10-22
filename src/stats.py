import os.path
from os.path import expanduser
from pathlib import Path, WindowsPath

import PySimpleGUI
import pandas as pd

statsfile = WindowsPath(expanduser('~/Documents')).joinpath("SBBTracker/stats.csv")

headings = ["Hero", "# Matches", "Avg Place", "Top 4", "Wins"]


def update_window(window: PySimpleGUI.Window, startinghero: str, endingHero: str, place: str):
    window.extend_layout(window["-StartingHero-"], [[PySimpleGUI.T(startinghero)]])
    window.extend_layout(window["-EndingHero-"], [[PySimpleGUI.T(endingHero)]])
    window.extend_layout(window["-Placement-"], [[PySimpleGUI.T(place)]])


def generate_stats(window: PySimpleGUI.Window, df: pd.DataFrame):
    df["Placement"] = pd.to_numeric(df["Placement"])
    for hero_type in ["StartingHero", "EndingHero"]:
        heroes = sorted(set(df[hero_type]))

        data = []
        for hero in heroes:
            if not hero.isspace():
                bool_df = df[hero_type] == hero
                total_matches = sum(bool_df)
                avg = round(df.loc[bool_df, 'Placement'].sum() / total_matches, 2)
                total_top4 = len(df.loc[bool_df & (df['Placement'] <= 4), 'Placement'])
                total_wins = len(df.loc[bool_df & (df['Placement'] <= 1), 'Placement'])
                data.append([hero, str(total_matches), str(avg), str(total_top4), str(total_wins)])

            key = f"-{hero_type}Stats-"
            table = window[key]
            table.update(values=data)


class PlayerStats:

    def __init__(self, window: PySimpleGUI.Window):
        self.window = window
        if os.path.exists(statsfile):
            self.df = pd.read_csv(str(statsfile))
            if 'Hero' in self.df.columns:
                #  Legacy data
                self.df = self.df.rename({'Hero': "EndingHero"}, axis='columns')
                self.df["StartingHero"] = " "
                self.df = self.df[["StartingHero", "EndingHero", "Placement"]]
            for row in self.df.itertuples():
                update_window(self.window, row.StartingHero, row.EndingHero, row.Placement)
            generate_stats(self.window, self.df)
        else:
            self.df = pd.DataFrame(columns=['StartingHero', 'EndingHero', 'Placement'])

    def export(self, filepath: Path):
        try:
            if not filepath.parent.exists():
                os.makedirs(filepath.parent)
            self.df.to_csv(str(filepath), index=False)
        except Exception as e:
            print(e)

    def save(self):
        self.export(statsfile)

    def update_stats(self, startinghero: str, endinghero: str, placement: str):
        self.df = self.df.append({"StartingHero": startinghero, "EndingHero": endinghero, "Placement": placement},
                                 ignore_index=True)
        update_window(self.window, startinghero, endinghero, placement)
        generate_stats(self.window, self.df)
