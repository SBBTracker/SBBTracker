import os.path

import PySimpleGUI
import pandas as pd

statsfile = "stats.pkl"


def update_window(window: PySimpleGUI.Window, hero: str, place: str):
    window.extend_layout(window["-Hero-"], [[PySimpleGUI.T(hero)]])
    window.extend_layout(window["-Placement-"], [[PySimpleGUI.T(place)]])


class PlayerStats:

    def __init__(self, window: PySimpleGUI.Window):
        self.window = window
        if os.path.exists(statsfile):
            self.df = pd.read_pickle(statsfile)
            for row in self.df.itertuples():
                update_window(self.window, row.Hero, row.Placement)
        else:
            self.df = pd.DataFrame(columns=['Hero', 'Placement'])

    def save(self):
        try:
            pd.to_pickle(self.df, statsfile)
        except Exception as e:
            print(e)

    def update_stats(self, hero: str, placement: str):
        self.df = self.df.append({"Hero": hero, "Placement": placement}, ignore_index=True)
        update_window(self.window, hero, placement)

    def export(self, filepath: str):
        try:
            self.df.to_csv(filepath, index=False)
        except:
            pass