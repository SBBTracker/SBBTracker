import copy

import numpy as np

from sbbtracker.parsers.log_parser import Action
from sbbtracker.utils.asset_utils import replace_template_ids

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
            # in the UI/ logs the slot is 0-6
            # in the sim the "position" is 1-7
            slot_orig+1: slot_dest+1,
            slot_dest+1: slot_orig+1,
        }
    )


def randomize_board(board):
    return apply_permutation(
        board,
        permute_map={
            orig: perm
            for orig, perm in zip(
                list(range(1, 8)), np.random.permutation(list(range(1, 8)))
            )
        }
    )


def apply_permutation(board, permute_map):
    print("APPLY PERMUTATION")
    # don't permute in place
    board_stated = Board(
        from_state(
            copy.deepcopy(
                replace_template_ids(
                    board
                )
            )
        )
    )
    board_stated("OnSetup")
    characters = board_stated.p1.valid_characters()
    board_stated.p1.despawn(*characters, kill=False)

    print(f"{permute_map=}")
    for character in characters:
        board_stated.p1.spawn(
            character,
            position=permute_map.get(character.position, character.position),
        )

    new_player_state = board_stated.p1.to_state()
    assert board_stated.p1.id == "player"

    new_player_board = []
    new_player_state["hero"]["zone"] = "Hero"
    new_player_board.append(Action.from_state(new_player_state["hero"]))

    for character in new_player_state["characters"]:
        character["zone"] = "Character"
        new_player_board.append(Action.from_state(character))

    for treasure in new_player_state["treasures"]:
        treasure["zone"] = "Treasure"
        new_player_board.append(Action.from_state(treasure))

    for spell in new_player_state["spells"]:
        spell["zone"] = "Spell"
        new_player_board.append(Action.from_state(spell))

    return {
        "player": new_player_board,
        "opponent": board["opponent"],
    }

