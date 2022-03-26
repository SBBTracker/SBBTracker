import json
import logging
import shutil
from tempfile import NamedTemporaryFile

from sbbtracker import paths

settings_file = paths.sbbtracker_folder.joinpath("settings.json")


def load():
    if settings_file.exists():
        try:
            with open(settings_file, "r") as json_file:
                return json.load(json_file)
        except Exception as e:
            logging.error("Couldn't load settings file!")
            logging.error(str(e))
    return {}


settings_dict = load()


class Setting:
    def __init__(self, key, default):
        self.key = key
        self.default = default


# hidden
filter_ = Setting("filter", "All Matches")
show_patch_notes = Setting("show-patch-notes", False)
player_id = Setting("player-id", False)
api_key = Setting("api-key", "")
prompt_data_collection = Setting("prompt-data-collection", True)
streamer_overlay_size = Setting("streamer-overlay-size", (0, 0))
# general
language = Setting("lang", "en")
live_palette = Setting("live-palette", "paired")
matchmaking_only = Setting("matchmaking-only", False)
save_stats = Setting("save-stats", True)
#data
upload_data = Setting("upload-data", False)
# overlay
boardcomp_transparency = Setting("boardcomp-transparency", 0)
simulator_transparency = Setting("simulator-transparency", 0)
monitor = Setting("monitor", 0)
enable_overlay = Setting("enable-overlay", False)
enable_sim = Setting("enable-sim", False)
enable_comps = Setting("enable-comps", True)
enable_turn_display = Setting("enable-turn-display", True)
enable_hero_stats = Setting("enable-hero-stats", True)
disable_scaling = Setting("disable-scaling", False)
overlay_comps_scaling = Setting("overlay-comps-scaling", 100)
overlay_comps_position = Setting("overlay-comps-position", (0,0))
hide_overlay_in_bg = Setting("hide-overlay-in-bg", False)
show_tracker_button = Setting("show-tracker-button", True)
simulator_position = Setting("simulator-position", (0, 0))
simulator_scale = Setting("simulator-scale", 100)
turn_indicator_position = Setting("turn-indicator-position", (0, 0))
number_simulations = Setting("number-simulations", 1000)
number_threads = Setting("number-threads", 3)
turn_display_font_size = Setting("turn-display-font-size", 25)
turn_display_transparency = Setting("turn_display_transparency", 0)
# streaming
streaming_mode = Setting("streaming-mode", False)
stream_overlay_color = Setting("stream-overlay-color", "#FF00FF")
streamable_score_list = Setting("streamable-score-list", False)
streamable_score_max_len = Setting("streamable-score-max-len", 20)
streamable_scores = Setting("streamable-scores", [])
# advanced
export_comp_button = Setting("export-comp-button", False)
show_ids = Setting("show-ids", False)
show_id_window = Setting("show-id-window", False)


def get(setting: Setting, default=None):
    if default is None:
        default = setting.default
    key = setting.key
    return settings_dict.setdefault(key, default)


def set_(setting: Setting, value):
    settings_dict[setting.key] = value
    return value


def toggle(setting: Setting):
    settings_dict[setting.key] = not settings_dict[setting.key]


def save():
    with NamedTemporaryFile(delete=False, mode='w', newline='') as temp_file:
        json.dump(settings_dict, temp_file, indent=2)
        temp_name = temp_file.name
    try:
        with open(temp_name) as file:
            json.load(file)
        shutil.move(temp_name, settings_file)
    except Exception as e:
        logging.error("Couldn't save settings correctly")
        logging.error(str(e))
