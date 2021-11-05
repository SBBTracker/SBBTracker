import math
import os.path
from datetime import datetime
from os.path import expanduser
from pathlib import Path

import PySimpleGUI
import pandas as pd

import asset_utils
from application_constants import Keys, stats_per_page

sbbtracker_folder = Path(expanduser('~/Documents')).joinpath("SBBTracker")
statsfile = Path(expanduser('~/Documents')).joinpath("SBBTracker/stats.csv")
if not sbbtracker_folder:
    sbbtracker_folder.mkdir()

headings = ["Hero", "# Matches", "Avg Place", "Top 4", "Wins"]


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

        key = Keys.StartingHeroStats if hero_type == "StartingHero" else Keys.EndingHeroStats
        table = window[key.value]
        padding = [["", "", "", ""] for _ in range(len(asset_utils.hero_ids) - len(data))]
        data = data + padding
        table.update(values=data)


def update_history(window: PySimpleGUI.Window, df: pd.DataFrame, page_number: int = 1):
    start_index = len(df.index) - stats_per_page * page_number
    end_index = len(df.index) - stats_per_page * (page_number - 1)
    adjusted_start = start_index if start_index > 0 else 0
    window[Keys.MatchStats.value].update(
        df[adjusted_start:end_index][::-1].loc[:, df.columns != 'Timestamp'].values.tolist())
    window[Keys.StatsPageNum.value].update(f"Page: {page_number}")


def get_num_pages(df: pd.DataFrame):
    return math.ceil(len(df.index) / stats_per_page)


class PlayerStats:

    def __init__(self, window: PySimpleGUI.Window):
        self.window = window
        if os.path.exists(statsfile):
            self.df = pd.read_csv(str(statsfile))
            if 'Hero' in self.df.columns:
                #  Legacy data
                self.df = self.df.rename({'Hero': "EndingHero"}, axis='columns')
                self.df["StartingHero"] = " "
                self.df = self.df[["StartingHero", "EndingHero", "Placement", "Timestamp"]]
            if 'Timestamp' not in self.df.columns:
                #  Pre-timestamp data gets an empty-timestamp column
                self.df["Timestamp"] = "1973-01-01"
            self.df['Timestamp'] = self.df['Timestamp'].replace(r'^\s*$', "1973-01-01", regex=True)
            update_history(self.window, self.df, 1)
            generate_stats(self.window, self.df)
        else:
            self.df = pd.DataFrame(columns=['StartingHero', 'EndingHero', 'Placement', 'Timestamp'])

    def export(self, filepath: Path):
        try:
            if not filepath.parent.exists():
                os.makedirs(filepath.parent)
            self.df.to_csv(str(filepath), index=False)
        except Exception as e:
            print(e)

    def save(self):
        self.export(statsfile)

    def delete(self):
        self.df = pd.DataFrame(columns=['StartingHero', 'EndingHero', 'Placement', 'Timestamp'])
        try:
            os.rename(statsfile, str(statsfile) + "_backup")
        except Exception as e:
            print("Unable to move old stats file!")
            print(e)
        update_history(self.window, self.df)
        data = [['' for __ in range(5)] for _ in range(len(asset_utils.hero_ids))]
        for hero_type in [Keys.StartingHeroStats, Keys.EndingHeroStats]:
            self.window[hero_type.value].update(data)

    def update_page(self, page_num: int):
        update_history(self.window, self.df, page_num)

    def update_stats(self, starting_hero: str, ending_hero: str, placement: str):
        self.df = self.df.append(
            {"StartingHero": starting_hero, "EndingHero": ending_hero, "Placement": placement,
             "Timestamp": datetime.now().strftime("%Y-%m-%d")},
            ignore_index=True)
        update_history(self.window, self.df)
        generate_stats(self.window, self.df)

    def filter(self, start_date: str, end_date: str):
        df = self.df
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d")
        if start_date == "1973-01-01":
            generate_stats(self.window, df)
        else:
            filtered = df[(df['Timestamp'] >= start_date) & (df['Timestamp'] <= end_date)]
            generate_stats(self.window, filtered)
