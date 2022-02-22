import json
import logging
import math
import os.path
import shutil
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
from construct import GreedyRange

from sbbtracker.utils import asset_utils
from sbbtracker.parsers import log_parser
import sbbtracker.paths as paths
from sbbtracker.parsers.record_parser import STRUCT_ACTION, id_to_action_name
from sbbtracker.paths import backup_dir, statsfile, stats_format


headings = ["Hero", "# Matches", "Avg Place", "Top 4", "Wins", "Net MMR"]
stats_per_page = 20

pd.options.mode.chained_assignment = None

stats_columns = ['StartingHero', 'EndingHero', 'Placement', 'Timestamp', '+/-MMR', 'SessionId']


def sorting_key(sort_col: int):
    """
    @param sort_col: the column to sort
    @return: the key function for sorting a column
    """
    if sort_col == 0:
        return str
    elif sort_col == 2:
        return lambda x: float(x) if float(x) > 0 else float("inf")
    else:
        return float


def adjust_legacy_df(df: pd.DataFrame):
    if 'SessionId' not in df.columns:
        df['SessionId'] = ' '
    if 'Timestamp' not in df.columns:
        #  Pre-timestamp data gets an empty-timestamp column
        df["Timestamp"] = "1973-01-01"
    if '+/-MMR' not in df.columns:
        #  Pre-MMR data gets 0 MMR for each game
        df["+/-MMR"] = "0"
    if 'Hero' in df.columns:
        #  Legacy data
        df = df.rename({'Hero': "EndingHero"}, axis='columns')
        df["StartingHero"] = " "
        df = df[stats_columns]
    #  clean up empty timestamps into some old time (that I thought was unix epoch but was off by 3 years lol)
    df['Timestamp'] = df['Timestamp'].replace(r'^\s*$', "1973-01-01", regex=True)
    #  Grandmother IS Big Bad Wolf
    df['EndingHero'] = df['EndingHero'].replace('Big Bad Wolf', 'Grandmother')
    for hero_type in ['StartingHero', 'EndingHero']:
        # The Sphinx was improperly named for a time
        df[hero_type] = df[hero_type].replace('Sphinx', 'The Sphinx')
    return df


def backup_stats(force=False):
    daily_file = backup_dir.joinpath("backup_" + date.today().strftime("%Y-%m-%d") + stats_format)
    if (not daily_file.exists() or force) and statsfile.exists():
        # we haven't written the backup today lets do it (or we're forcing an overwrite)
        backups = list(backup_dir.glob("backup*.csv"))
        backups.sort(reverse=True)
        shutil.copy(statsfile, daily_file)
        if len(backups) > 7:
            # we have reached the max number of backups, delete the oldest ones
            for old_backup in backups[-(len(backups) - 7):]:
                os.remove(old_backup)


def most_recent_backup_date():
    backups = list(backup_dir.glob("backup*.csv"))
    if backups:
        sorted_by_recent = sorted(backups, key=os.path.getmtime, reverse=True)
        timestamp = os.path.getmtime(sorted_by_recent[0])
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    else:
        return "Never"


class PlayerStats:
    """
    A class for loading, storing, and manipulating a player's match history and its relevant stats
    """
    def __init__(self):
        if os.path.exists(statsfile):
            try:
                self.df = pd.read_csv(str(statsfile))
                self.df = adjust_legacy_df(self.df)
                if not set(stats_columns).issubset(self.df.columns):
                    self.df = pd.read_csv(os.listdir(backup_dir)[0])
                    self.df = adjust_legacy_df(self.df)
            except:
                logging.exception("Error loading stats file. Attempting to load backup.")
                try:
                    self.df = pd.read_csv(os.listdir(backup_dir)[0])
                except:
                    logging.exception("Couldn't load backup. Starting a new stats file")
                    self.df = pd.DataFrame(columns=stats_columns)
        else:
            self.df = pd.DataFrame(columns=stats_columns)
        self.df = self.df.dropna()  # cleanup any weird stats

    def export(self, filepath: Path):
        self.df.to_csv(filepath, index=False)

    def save(self):
        backup_stats()
        with NamedTemporaryFile(delete=False, mode='w', newline='') as temp_file:
            self.df.to_csv(temp_file, index=False)
            temp_name = temp_file.name
        try:
            with open(temp_name) as file:
                df = pd.read_csv(file)
            if set(stats_columns).issubset(df.columns):
                shutil.move(temp_name, statsfile)
        except:
            logging.exception("Couldn't save settings correctly")

    def delete(self):
        self.df = pd.DataFrame(columns=stats_columns)

    def get_num_pages(self):
        return math.ceil(len(self.df.index) / stats_per_page)

    def get_page(self, page_num: int):
        start_index = len(self.df.index) - stats_per_page * page_num
        end_index = len(self.df.index) - stats_per_page * (page_num - 1)
        adjusted_start = start_index if start_index > 0 else 0
        match_stats = self.df[adjusted_start:end_index][::-1].loc[:, self.df.columns != 'Timestamp'].values.tolist()
        padding = [["", "", "", "", ""] for _ in range(stats_per_page - len(match_stats))]
        match_stats += padding
        return match_stats

    def update_stats(self, starting_hero: str, ending_hero: str, placement: str, mmr_change: str, session_id: str,
                     timestamp: date = None):
        if session_id not in self.df['SessionId'].values and starting_hero and ending_hero and placement \
                and mmr_change and session_id:
            if timestamp is None:
                timestamp = datetime.now()
            if ending_hero == "Big Bad Wolf":
                ending_hero = "Grandmother"
            self.df = self.df.append(
                {"StartingHero": starting_hero, "EndingHero": ending_hero, "Placement": placement,
                 "Timestamp": timestamp.strftime("%Y-%m-%d"), "+/-MMR": str(mmr_change), "SessionId": session_id},
                ignore_index=True)
        else:
            logging.warning("Not adding existing match!")

    def generate_stats(self, sort_col: int, sort_asc: bool, df=None):
        if df is None:
            df = self.df
        df["Placement"] = pd.to_numeric(df["Placement"])
        df["+/-MMR"] = pd.to_numeric(df["+/-MMR"])
        stats = []
        for hero_type in ["StartingHero", "EndingHero"]:
            data = []
            for value in asset_utils.content_id_lookup.values():
                hero = value['Name']
                heroid = value['Id']
                if heroid.startswith("SBB_HERO") and hero != "Big Bad Wolf":
                    bool_df = df[hero_type] == hero
                    total_matches = sum(bool_df)
                    avg = round(df.loc[bool_df, 'Placement'].mean(), 2)
                    if math.isnan(avg):
                        avg = 0
                    total_top4 = len(df.loc[bool_df & (df['Placement'] <= 4), 'Placement'])
                    total_wins = len(df.loc[bool_df & (df['Placement'] == 1), 'Placement'])
                    net_mmr = df.loc[bool_df, '+/-MMR'].sum()
                    data.append([hero, str(total_matches), str(avg), str(total_top4), str(total_wins), str(net_mmr)])

            padding = [["", "", "", "", "", ""] for _ in range(asset_utils.get_num_heroes() - len(data))]
            data = data + padding
            global_matches = len(df)
            global_avg = round(df["Placement"].mean(), 2)
            if math.isnan(global_avg):
                global_avg = 0
            global_top4 = len(df.loc[df['Placement'] <= 4, 'Placement'])
            global_wins = len(df.loc[df['Placement'] == 1, 'Placement'])
            global_net_mmr = df["+/-MMR"].sum()

            sorter = sorting_key(sort_col)
            data = sorted(data, key=lambda x: sorter(x[sort_col]), reverse=sort_asc)
            data.insert(0, ["All Heroes", str(global_matches), str(global_avg), str(global_top4), str(global_wins),
                            str(global_net_mmr)])
            stats.append(data)
        return stats

    def filter(self, start_date, end_date, sort_col: int, sort_asc: bool):
        df = self.df
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d")
        if str(start_date) <= "1973-01-01":
            return self.generate_stats(sort_col, sort_asc)
        else:
            filtered = df[(df['Timestamp'] >= start_date) & (df['Timestamp'] <= end_date)]
            return self.generate_stats(sort_col, sort_asc, filtered)

    def delete_entry(self, row, reverse=False):
        index = len(self.df.index) - row - 1 if reverse else row
        self.df = self.df.drop(self.df.index[index])

    def import_matches(self, progress_handler=None):
        save_dir = paths.sbb_root
        filenames = save_dir.glob("record_*.txt")
        sorted_by_recent = sorted(filenames, key=os.path.getctime)
        i = 0
        for game in sorted_by_recent:
            match = extract_endgame_stats_from_record_file(game)
            if match:
                # print(match)
                self.update_stats(*match)
            if progress_handler:
                progress_handler(i, len(sorted_by_recent) - 1)
                i += 1

    def save_combats(self, combat_info, session_id):
        match_file = paths.matches_dir.joinpath(f"{session_id}.json")
        with open(match_file, 'w') as f:
            json.dump(combat_info, f)


def extract_endgame_stats_from_record_file(filename):
    with open(filename, 'rb') as f:
        result = GreedyRange(STRUCT_ACTION).parse_stream(f)
        remaining_binary_contents = f.read()
    if len(remaining_binary_contents) != 0:
        return
    starting_hero = None
    ending_hero = None
    mmr_change = 0
    game_over = False
    session_id = None
    placement = None
    player_id = None
    timestamp = datetime.fromtimestamp(os.path.getmtime(filename))
    player_names = set()
    hero_names = set()
    bot_game = False

    for record in result:
        action_name = id_to_action_name[record.action_id]
        if action_name in log_parser.EVENT_ADDPLAYER:
            hero_names.add(asset_utils.get_card_name(str(record.template_id)))
            player_names.add(record.player_name)
            bot_game = len(hero_names.intersection(player_names)) == 7
        if action_name in log_parser.EVENT_CONNINFO:
            session_id = record.session_id
        if not game_over and action_name in log_parser.EVENT_ADDPLAYER and starting_hero is None:
            starting_hero = asset_utils.get_card_name(str(record.template_id))
            player_id = record.player_id
        if action_name in log_parser.EVENT_ENTERRESULTSPHASE:
            game_over = True
            mmr_change = record.rank_reward
        if game_over and action_name in log_parser.EVENT_ADDPLAYER and player_id == record.player_id:
            ending_hero = asset_utils.get_card_name(str(record.template_id))
            placement = record.place
    results = (starting_hero, ending_hero, placement, mmr_change, session_id, timestamp)
    if all(result is not None and results != "" for result in results) and not bot_game:
        return results
