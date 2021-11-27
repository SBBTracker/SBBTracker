from pathlib import Path

hero_ids = {
    "SBB_HERO_APOCALYPSE": "Apocalypse",
    "SBB_HERO_PRINCESSBELLE": "Beauty",
    "SBB_HERO_BIGBADWOLF": "Big Bad Wolf",
    "SBB_HERO_THECOLLECTOR": "Celestial Tiger",
    "SBB_HERO_CHARON": "Charon",
    "SBB_HERO_DARKONE": "Evella",
    "SBB_HERO_FALLENANGEL": "Fallen Angel",
    "SBB_HERO_GEPETTO": "Geppetto",
    "SBB_HERO_OLDGRANNY": "Grandmother",
    "SBB_HERO_GWEN": "Gwen",
    "SBB_HERO_HORDEDRAGON": "Hoard Dragon",
    "SBB_HERO_SIRPIPS": "Jack's Giant",
    # "SBB_HERO_KINGMIDAS": "King Midas",
    "SBB_HERO_KRAMPUS": "Krampus",
    "SBB_HERO_LOKI": "Loki",
    "SBB_HERO_MADCATTER": "Mad Catter",
    "SBB_HERO_MASK": "Mask",
    "SBB_HERO_MERLIN": "Merlin",
    "SBB_HERO_KINGLION": "Mihri, King Lion",
    "SBB_HERO_MORDRED": "Mordred",
    "SBB_HERO_MORGANLEFAY": "Morgan le Fay",
    # "SBB_HERO_MOTHER_MOOSE": "Mother Moose",
    "SBB_HERO_MRSCLAUS": "Mrs. Claus",
    "SBB_HERO_MUERTE": "Muerte",
    # "SBB_HERO_NEMESIS": "Nemesis",
    "SBB_HERO_CARDCHEAT": "Pan's Shadow",
    "SBB_HERO_PETERPAN": "Peter Pants",
    "SBB_HERO_PIEDPIPER": "Pied Piper",
    "SBB_HERO_POTIONMASTER": "Potion Master",
    "SBB_HERO_GANDALF": "Pup the Magic Dragon",
    "SBB_HERO_DRACULA": "Sad Dracula",
    "SBB_HERO_SIRGALAHAD": "Sir Galahad",
    "SBB_HERO_SKIP,THETIMESKIPPER": "Skip, the Time Skipper",
    "SBB_HERO_MAIDMARIAN": "Snow Angel",
    "SBB_HERO_THEGREEDCURSED": "The Cursed King",
    "SBB_HERO_FATE": "The Fates",
    "SBB_HERO_BLACKKNIGHT": "The Headless Horseman",
    "SBB_HERO_MILITARYLEADER": "Trophy Hunter",
    "SBB_HERO_WONDERWADDLE": "Wonder Waddle",
    "SBB_HERO_BIGDEAL": "Xelhua",
}

character_ids = {
    # Characters
    "SBB_CHARACTER_DUMBLEDWARF": "Dubly",
}
content_id_lookup = hero_ids | character_ids


def get_card_art_name(content_id: str, display_text: str):
    """
    Map the content ID to the card to prevent issues with skins/renames.
    :param content_id: content_id of the card, e.g. SBB_HERO_GWEN
    :param display_text: the displayed text of a card
    :return: the base card art name if found, otherwise 'display_text'
    """
    return content_id_lookup.get(content_id, display_text)


def get_card_path(card_name: str, content_id: str, is_golden: bool):
    """
    Gets the path for the card asset
    :param card_name: the display name of a card
    :param content_id: the content id of the card, e.g. SBB_HERO_GWEN
    :param is_golden: if the card is golden or not
    :return: the path card art if it exists, otherwise path to the blank resource
    """
    assets_path = Path("../cards/")
    # what the fuck is this
    actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
    input_content_id = content_id
    if actually_is_golden:
        input_content_id = input_content_id[7:]  # Skipping the "GOLDEN_"
    # asset_name = get_card_art_name(input_content_id, card_name)
    asset_name = input_content_id
    # path = assets_path.joinpath(asset_name.replace("'", "_") + (" upgraded" if actually_is_golden else "") + ".png")
    path = assets_path.joinpath(asset_name.replace("'", "_") + ".png")
    if not path.exists() or asset_name == "empty":
        path = Path("../assets/").joinpath("Empty.png")
    return str(path)
