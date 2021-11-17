import math
import os.path
from datetime import datetime
from os.path import expanduser
from pathlib import Path

import pandas as pd

import asset_utils
from application_constants import Keys, stats_per_page

sbbtracker_folder = Path(expanduser('~/Documents')).joinpath("SBBTracker")
statsfile = Path(expanduser('~/Documents')).joinpath("SBBTracker/stats.csv")
if not sbbtracker_folder:
    sbbtracker_folder.mkdir()

headings = ["Hero", "# Matches", "Avg Place", "Top 4", "Wins"]


class PlayerStats:

    def __init__(self):
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
            if '+/-MMR' not in self.df.columns:
                #  Pre-MMR data gets 0 MMR for each game
                self.df["+/-MMR"] = "0"
            #  clean up empty timestamps into some old time (that I thought was unix epoch but was off by 3 years lol)
            self.df['Timestamp'] = self.df['Timestamp'].replace(r'^\s*$', "1973-01-01", regex=True)
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
        except:
            print("Unable to move old stats file!")

    def get_num_pages(self):
        return math.ceil(len(self.df.index) / stats_per_page)

    def get_page(self, page_num: int):
        start_index = len(self.df.index) - stats_per_page * page_num
        end_index = len(self.df.index) - stats_per_page * (page_num - 1)
        adjusted_start = start_index if start_index > 0 else 0
        match_stats = self.df[adjusted_start:end_index][::-1].loc[:, self.df.columns != 'Timestamp'].values.tolist()
        return match_stats

    def update_stats(self, starting_hero: str, ending_hero: str, placement: str, mmr_change: str):
        self.df = self.df.append(
            {"StartingHero": starting_hero, "EndingHero": ending_hero, "Placement": placement,
             "Timestamp": datetime.now().strftime("%Y-%m-%d"), "+/-MMR": str(mmr_change)},
            ignore_index=True)

    def generate_stats(self, df=None):
        if df is None:
            df = self.df
        df["Placement"] = pd.to_numeric(df["Placement"])
        stats = []
        for hero_type in ["StartingHero", "EndingHero"]:
            # heroes = sorted(set(df[hero_type]))

            data = []
            for hero in asset_utils.hero_ids.values():
                if not hero.isspace():
                    bool_df = df[hero_type] == hero
                    total_matches = sum(bool_df)
                    avg = round(df.loc[bool_df, 'Placement'].mean(), 2)
                    if math.isnan(avg):
                        avg = 0
                    total_top4 = len(df.loc[bool_df & (df['Placement'] <= 4), 'Placement'])
                    total_wins = len(df.loc[bool_df & (df['Placement'] == 1), 'Placement'])
                    data.append([hero, str(total_matches), str(avg), str(total_top4), str(total_wins)])

            key = Keys.StartingHeroStats if hero_type == "StartingHero" else Keys.EndingHeroStats
            padding = [["", "", "", "", ""] for _ in range(len(asset_utils.hero_ids) - len(data))]
            data = data + padding
            global_matches = len(df)
            global_avg = round(df["Placement"].mean(), 2)
            global_top4 = len(df.loc[df['Placement'] <= 4, 'Placement'])
            global_wins = len(df.loc[df['Placement'] == 1, 'Placement'])
            data.insert(0, ["All Heroes", global_matches, global_avg, global_top4, global_wins])
            stats.append(data)
        return stats

    def filter(self, start_date: str, end_date: str):
        df = self.df
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d")
        if start_date == "1973-01-01":
            return self.generate_stats()
        else:
            filtered = df[(df['Timestamp'] >= start_date) & (df['Timestamp'] <= end_date)]
            return self.generate_stats(filtered)
