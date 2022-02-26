import copy

import numpy as np

from log_parser import Action

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
            orig: perm
            for orig, perm in zip(
                list(range(7)), np.random.permutation(7)
            )
        }
    )


def apply_permutation(board, permute_map):
    # don't permute in place
    board = copy.deepcopy(board)
    board_stated = Board(from_state(board))
    characters = board_stated.p1.valid_characters()
    board_stated.p1.despawn(*characters, kill=False)

    print(f"{permute_map=}")
    for character in characters:
        board_stated.p1.spawn(
            character, position=permute_map[charater.positon]
        )

    new_player_state = board_stated.p1.to_state()
    new_player_board = []

    new_player_state["hero"]["zone"] = "Hero"
    new_player_board.append(Action.from_state(new_player_state["hero"]))

    for character in new_player_state["character"]:
        treasure["zone"] = "Character"
        new_player_board.append(Action.from_state(character))

    for treasure in new_player_state["treasures"]:
        treasure["zone"] = "Treasure"
        new_player_board.append(Action.from_state(treasure))

    for spell in new_player_state["spells"]:
        treasure["zone"] = "Spells"
        new_player_board.append(Action.from_state(spell))

    board["player"] = new_player_board
    return board

