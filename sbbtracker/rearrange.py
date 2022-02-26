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


    board["player"] =

    # TODO pass level from original to rearranged board
    # When doing this, apply ZONE

    [
        Action.from_state(state)
        for state in board_stated.p1.to_state()
        for card in state.values()
        `]
        {
            'characters': characters,
            'treasures': treasures,
            'hero': hero,
            'spells': spells,
            'level': level,
            'hand': hand
        }
    return board

