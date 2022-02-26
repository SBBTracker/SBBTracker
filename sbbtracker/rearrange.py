import copy

import numpy as np

from sbbbattlesim.characters import registry as character_registry
from sbbbattlesim.heroes import registry as hero_registry
from sbbbattlesim.treasures import registry as treasure_registry


def make_swap(
    board,
    slot_orig,
    slot_dest,
):
    # don't permute in place
    board = copy.deepcopy(board)
    board["player"] = apply_buffs(board["player"], remove=True)
    permute_map = {
        slot_orig: slot_dest,
        slot_dest: slot_orig
    }
    print(f"{permute_map=}")
    # TODO add a layer unapply support buffs (before) and re-apply (after) permuting
    for character in board["player"]:
        if character.zone == "Character" and character.slot in permute_map:
            character.slot = permute_map[character.slot]
    board["player"] = apply_buffs(board["player"])
    return board


def randomize_board(board):
    board = copy.deepcopy(board)
    board["player"] = apply_buffs(board["player"], remove=True)
    player_permute_map = {
        str(orig): str(perm)
        for orig, perm in zip(
            list(range(7)), np.random.permutation(7)
        )
    }
    print(f"Random restart: {player_permute_map=}")
    for character in board["player"]:
        if character.zone == "Character" and character.slot in player_permute_map:
            character.slot = player_permute_map[character.slot]

    board["player"] = apply_buffs(board["player"])
    return board


def apply_buffs(board, remove=False):
    apply_or_remove = -1 if remove else 1
    hero = next(character.content_id for character in board if character.zone == "Hero")

    # TREASURES
    treasures = [
        treasure_registry[character.content_id]
        for character in board
        if character.zone == "Treasure"
    ]
    auras = [treasure for treasure in treasures if hasattr(treasure, "aura")]
    # mimic + celestial tiger
    treasure_multiplier = 1
    if hero == "SBB_HERO_THECOLLECTOR":
        treasure_multiplier *= 2.0
    if "SBB_TREASURE_TREASURECHEST" in treasures:
        treasure_multiplier *= 2.0
    for character in board:
        if character.zone == "Character":
            if character.slot == "0":
                for aura in auras:
                    character.attack = str(
                        int(character.attack) + apply_or_remove*(aura.attack*treasure_multiplier)
                    )
                    character.health = str(
                        int(character.health) + apply_or_remove*(aura.health*treasure_multiplier)
                    )

    # SUPPORTS
    buffs = {str(slot): {"attack": 0, "health": 0} for slot in range(4)}
    # pup
    pup_buff = (
        {"attack": 2, "health": 1}
        if hero == "SBB_HERO_GANDALF"
        else {"attack": 0, "health": 0}
    )


    # Horn of Olympus
    horn = "SBB_TREASURE_BANNEROFCOMMAND" in treasures
    evil_eye = 2 if "SBB_TREASURE_BANNEROFCOMMAND" in treasures else 1
    mimic = 2 if "SBB_TREASURE_TREASURECHEST" in treasures else 1

    if evil_eye and mimic:
        treasure_multiplier = 4
    elif evil_eye:
        treasure_multiplier = 2
    else:
        treasure_multiplier = 1

    characters = {
        character.slot: character_registry[character.content_id]
        for character in board
        if character.zone == "Character"
    }
    print(characters['1']._action_history)
    for slot, character in characters.items():
        if hasattr(character, "support"):
            if int(slot) < 4:
                # skip front-row supports
                continue
            if horn:
                iterator = buffs.items()
            else:
                support_slots = [str(int(slot) - i) for i in [3, 4]]
                iterator = zip(
                    support_slots, [buffs[i] for i in support_slots]
                )

            for slot, buff in buffs.items():
                # if character.support.character[slot].subtypes
                buff["attack"] += (
                    (character.support.attack + pup_buff["attack"]) * treasure_multiplier
                )
                buff["health"] += (
                    (character.support.health + pup_buff["health"]) * treasure_multiplier
                )

    for character in board:
        if character.zone == "Character":
            if character.slot in buffs:
                character.attack = str(
                    int(character.attack) + apply_or_remove * buff[character.slot]["attack"]
                )
                character.health = str(
                    int(character.health) + apply_or_remove * buff[character.slot]["health"]
                )


    return board



