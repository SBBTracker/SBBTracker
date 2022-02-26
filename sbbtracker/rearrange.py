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
            str(orig): str(perm)
            for orig, perm in zip(
                list(range(7)), np.random.permutation(7)
            )
        }
    )


def apply_permutation(board, permute_map):
    # don't permute in place
    board = copy.deepcopy(board)
    board_stated = Board(from_state(board))
    for character in board_stated.p1.valid_characters():
        for action in character._action_history:
            if action.temp:
                action.roll_back()

    print(f"{permute_map=}")
    board_stated.p1.rearrange(permute_map)
    board_stated.p1.board.register(PlayerOnSetup, source=board_stated.p1, priority=0)
    board["player"] = [Action.from_state(state) for state in board_stated.p1.to_state()]

    return board

