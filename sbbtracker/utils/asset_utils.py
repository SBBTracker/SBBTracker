import copy
import json
import logging
import sys
import os
from collections import namedtuple
from pathlib import Path

import pandas as pd

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True and sets the app
    # path into variable _MEIPASS'.
    application_path = Path(sys._MEIPASS)
else:
    application_path = Path(__file__).parent.parent

def get_asset(asset_name: str):
    return str(application_path.joinpath(f"../assets/{asset_name}"))

content_id_lookup = {}
hero_list = []
skin_mapping = { # mapping of the skin names to hero, manually collected...
    "RagnaROCK": "Apocalypse",
    "SeveredSoul": "FallenAngel",
    "DragonSculptor": "Geppetto",
    "DragonMotherGwen": "Gwen",
    "SpectralDragon": "HoardDragon",
    "MorganOfTheRose": "MorganleFay",
    "SuperPan": "PeterPants",
    "TrashPanda": "PotionMaster",
    "CircusPup": "PuptheMagicDragon",
    "Dr.Acula": "SadDracula",
    "FestiveDracula": "SadDracula",
    "ThreeLittleWitches": "TheFates",
    "ThreeOldWitches": "TheFates",
    "FrozenPhoenix": "WonderWaddle"
}
# headers:
# Id|InPool|Name|Cost|Level|Attack|Health|Game Text|Golden or regular|Type|Subtypes|Keywords
with open(get_asset("CardFile.txt"), "r") as card_file:
    cardfile_df = pd.read_csv(card_file, delimiter='|')
    for index, row in cardfile_df.iterrows():
        if "Hero" == row["Type"]:
            hero_list.append({ "Id": row["Id"], "Name": row["Name"], "InPool": row["InPool"] })
        name = row["Name"].replace(' ', '')
        if name in content_id_lookup:
            continue
        subtypes = row["Subtypes"].split(" - ") if isinstance(row["Subtypes"], str) else []
        content_id_lookup[name] = { "Id": row["Id"].replace("GOLDEN_", ""), "Name": row["Name"], "InPool": row["InPool"],
                                    "Subtypes": subtypes}


def get_card_data(card_name: str):
    """
    Map the card name (without spaces) to the cards info dict
    Will attempt to shift a hero skin to the default name
    @param card_name: card name (without spaces)
    @return: a dict of the card data
    """
    real_index = skin_mapping.get(card_name, card_name)
    return content_id_lookup[real_index]

def get_card_content_id(card_name: str):
    """
    Map the card name from the log file to the content id (e.g. SBB_HERO_GWEN)
    :param card_name: name of the card (without spaces), e.g. WonderWaddle
    :return: the base card art id
    """
    try:
        return get_card_data(card_name)["Id"]
    except TypeError:
        logging.error(card_name)
        return ""


def get_card_name(card_name: str):
    try:
        return get_card_data(card_name)["Name"]
    except TypeError:
        logging.error(card_name)
        return ""


def get_num_heroes():
    return len([v for v in hero_list if v["InPool"]])

def get_card_path(content_id: str):
    """
    Gets the path for the card asset
    :param content_id: the content id of the card, e.g. SBB_HERO_GWEN
    :return: the path card art if it exists, otherwise path to the blank resource
    """
    cards_path = application_path.joinpath("../cards/")
    input_content_id = get_card_content_id(content_id)
    asset_name = input_content_id
    path = cards_path.joinpath(asset_name + ".png")
    if not path.exists() or asset_name == "empty":
        path = Path("../../assets/").joinpath("Empty.png")
    return str(path)


def replace_template_ids(state):
    copied = copy.deepcopy(state)
    for playerid in copied:
        for character in copied[playerid]:
            templateid = character.content_id
            character.content_id = get_card_content_id(templateid)
            if hasattr(character, "health") and character.health <= 0:
                character.content_id = ""
            if character.subtypes is None:
                character.subtypes = get_subtypes(templateid)
    return copied


def get_subtypes(template_id):
    try:
        return content_id_lookup.get(template_id)["Subtypes"]
    except TypeError:
        logging.error(template_id)
        return ""