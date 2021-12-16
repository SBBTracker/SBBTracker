import json
import os
from pathlib import Path

try:
    with open("../assets/template-ids.json", "r") as json_file:
        content_id_lookup = json.load(json_file)
except:
    pass


def get_card_art_name(content_id: str, is_golden: bool):
    """
    Map the content ID to the card to prevent issues with skins/renames.
    :param content_id: content_id of the card, e.g. SBB_HERO_GWEN
    :return: the base card art name
    """
    try:
        return content_id_lookup.get(str(int(content_id) - int(is_golden)))["Id"]
    except TypeError:
        print(content_id)
        return ""


def get_hero_name(content_id: str):
    return content_id_lookup.get(str(content_id))["Name"]


def get_num_heroes():
    return len([v for v in content_id_lookup.values() if v['Id'].startswith("SBB_HERO")])


def get_asset(asset_name: str):
    return str(Path(__file__).parent.joinpath(f"../assets/{asset_name}"))


def get_card_path(content_id: str, is_golden: bool):
    """
    Gets the path for the card asset
    :param content_id: the content id of the card, e.g. SBB_HERO_GWEN
    :param is_golden: if the card is golden or not
    :return: the path card art if it exists, otherwise path to the blank resource
    """
    cards_path = Path(__file__).parent.joinpath("../cards/")
    # what the fuck is this
    actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
    input_content_id = get_card_art_name(content_id, actually_is_golden)
    asset_name = input_content_id
    path = cards_path.joinpath(asset_name.replace("'", "_") + ".png")
    if not path.exists() or asset_name == "empty":
        path = Path("../assets/").joinpath("Empty.png")
    return str(path)

