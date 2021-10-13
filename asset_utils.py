import os
from pathlib import Path

content_id_lookup = {
    # Heroes
    "SBB_HERO_MORGANLEFAY": "Morgan Le Fay",
    "SBB_HERO_DRACULA": "Sad Dracula",
    "SBB_HERO_GWEN": "Gwen",
    "SBB_HERO_PETERPAN": "Peter Pants",

    # Characters
    "SBB_CHARACTER_DUMBLEDWARF": "Dubly",
}


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
    assets_path = Path(os.environ["APPDATA"]).joinpath("SBBTracker/assets/cards/")
    # what the fuck is this
    actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
    asset_name = get_card_art_name(content_id, card_name)
    path = assets_path.joinpath(asset_name.replace("'", "_") + (" upgraded" if actually_is_golden else "") + ".png")
    if not path.exists() or asset_name == "empty":
        path = assets_path.joinpath("Empty.png")
    return str(path)
