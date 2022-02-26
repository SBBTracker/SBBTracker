import copy

import numpy as np

from sbbbattlesim.board import Board
from sbbbattlesim.characters import registry as character_registry
from sbbbattlesim.heroes import registry as hero_registry
from sbbbattlesim.player import PlayerOnSetup
from sbbbattlesim.simulate import from_state
from sbbbattlesim.treasures import registry as treasure_registry


def make_swap(
    board,
    slot_orig,
    slot_dest,
):
    return apply_permutation(
        board,
        permute_map = {
            slot_orig: slot_dest,
            slot_dest: slot_orig
        }
    )


def randomize_board(board):
    return apply_permutation(
        board,
        permute_map={
            str(orig): str(perm)
            for orig, perm in zip(
                list(range(7)), np.random.permutation(7)
            )
        }
    )


def apply_permutation(board, permute_map):
    # don't permute in place
    board = copy.deepcopy(board)
    board_state = Board(from_state(board))
    for character in board_state.p1.valid_characters():
        for action in character._action_history:
            if action.temp:
                action.roll_back()

    print(f"{permute_map=}")
    temp_characters = {i: None for i in range(1, 8)}
    for slot, character in board_state.p1._characters.items():
        if str(slot) in permute_map:
            temp_characters[int(permute_map[str(slot)])] = character
    board_state.p1._characters = temp_characters

    board_state.p1.board.register(PlayerOnSetup, source=board_state.p1, priority=0)
    board["player"] = [
        card for card in board["player"] if card.zone != "Character"
    ] + list(board_state.p1._characters.values())
    return board





# Unused hackery
def apply_buffs(board, remove=False):
    board_data = from_state(board)
    apply_or_remove = -1 if remove else 1
    hero = next(character.content_id for character in board if character.zone == "Hero")

    # TREASURES
    treasures = [
        treasure_registry[treasure.content_id](**treasure)
        for treasure in board_data["player"]["treasures"]
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
        character.slot: character_registry[character.content_id](**character)
        for character in board_data["player"]["characters"]
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



