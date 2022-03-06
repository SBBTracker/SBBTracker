import os
import platform
import shutil
from os.path import expanduser
from pathlib import Path

os_name = platform.system()

# SBBTracker paths
old_sbbtracker_folder = Path(expanduser('~/Documents')).joinpath("SBBTracker")
if "Windows" == os_name:
    sbbtracker_folder = Path(os.getenv('APPDATA')).joinpath("SBBTracker")
else:
    sbbtracker_folder = old_sbbtracker_folder
stats_format = ".csv"
statsfile = sbbtracker_folder.joinpath("stats" + stats_format)
backup_dir = Path(sbbtracker_folder).joinpath("backups")
if not sbbtracker_folder.exists():
    if old_sbbtracker_folder.exists() and os_name == "Windows":
        #  Found the legacy folder
        shutil.copytree(old_sbbtracker_folder, sbbtracker_folder, dirs_exist_ok=True)
    else:
        sbbtracker_folder.mkdir()

if not backup_dir.exists():
    backup_dir.mkdir()

offsetfile = sbbtracker_folder.joinpath("logfile.offset")
if not offsetfile.exists():
    offsetfile.touch()

matches_dir = sbbtracker_folder.joinpath("matches")
if not matches_dir.exists():
    matches_dir.mkdir()


# Storybook Brawl paths
if os_name == 'Linux':
    sbb_root = Path(expanduser("~/.steam/steam/steamapps/compatdata/1367020/pfx/drive_c/users/steamuser"
                               "/AppData/LocalLow/Good Luck Games/Storybook Brawl"))
elif os_name == "Windows":
    sbb_root = Path(os.environ["LOCALAPPDATA"]).parent.joinpath("LocalLow/Good Luck Games/Storybook Brawl")
elif os_name == "Darwin":
    pass  # todo: implement Mac
logfile = sbb_root.joinpath("Player.log")
