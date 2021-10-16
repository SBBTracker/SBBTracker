import os.path
from pathlib import Path

import PySimpleGUI
import pandas as pd

statsfile = Path(os.environ["APPDATA"]).joinpath("stats.csv")


def update_window(window: PySimpleGUI.Window, hero: str, place: str):
    window.extend_layout(window["-Hero-"], [[PySimpleGUI.T(hero)]])
    window.extend_layout(window["-Placement-"], [[PySimpleGUI.T(place)]])


class PlayerStats:

    def __init__(self, window: PySimpleGUI.Window):
        self.window = window
        if os.path.exists(statsfile):
            self.df = pd.read_csv(str(statsfile))
            for row in self.df.itertuples():
                update_window(self.window, row.Hero, row.Placement)
        else:
            self.df = pd.DataFrame(columns=['Hero', 'Placement'])

    def export(self, filepath: Path):
        try:
            if not filepath.parent.exists():
                os.makedirs(filepath)
            self.df.to_csv(str(filepath), index=False)
        except Exception as e:
            print(e)

    def save(self):
        self.export(statsfile)

    def update_stats(self, hero: str, placement: str):
        self.df = self.df.append({"Hero": hero, "Placement": placement}, ignore_index=True)
        update_window(self.window, hero, placement)
