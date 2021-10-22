#!/usr/bin/python3
import operator
import os
import sys
import threading
import webbrowser
from enum import Enum
from pathlib import Path

import PySimpleGUI as sg

import log_parser
import asset_utils
import stats
import update_check
from stats import PlayerStats

player_ids = []
board_indicies = []

art_dim = (161, 204)


# 161 x 204


class Slot(Enum):
    Char1 = 0
    Char2 = 1
    Char3 = 2
    Char4 = 3
    Char5 = 4
    Char6 = 5
    Char7 = 6
    Treasure1 = 7
    Treasure2 = 8
    Treasure3 = 9
    Spell = 10
    Hero = 11


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.join(os.path.abspath(".."), relative_path)


def get_tab_key(index: int):
    return f"-tab{index}-"


def get_graph_key(index: int):
    return f"-graph{index}-"


graph_ids = {str(player): {str(slot.value): {} for slot in Slot} for player in range(0, 9)}


def update_player(window: sg.Window, update: log_parser.Update):
    state = update.state
    index = get_player_index(state.playerid)
    player_tab = window[get_tab_key(index)]
    real_hero_name = asset_utils.get_card_art_name(state.heroid, state.heroname)
    title = f"{real_hero_name}" if state.health > 0 else f"{real_hero_name} *DEAD*"
    player_tab.update(title=title)
    update_card(window, state.playerid, 11, state.heroname, state.heroid, state.health, "", False)


def update_board(window: sg.Window, update: log_parser.Update):
    for playerid, actions in update.state.items():
        used_slots = []
        for action in actions:
            slot = action.slot
            zone = action.zone
            position = 10 if zone == 'Spell' else (7 + int(slot)) if zone == "Treasure" else slot
            update_card(window, playerid, position, action.cardname, action.content_id, action.cardhealth,
                        action.cardattack, action.is_golden)
            used_slots.append(str(position))
        all_slots = [str(slot.value) for slot in Slot]

        unused_slots = set(all_slots) - set(used_slots)
        for slot in unused_slots:
            update_card(window, playerid, slot, "empty", "", "", "", False)


def get_image_location(position: int):
    if position < 4:
        x = (161 * position) + 300
        y = 0
    elif 4 <= position < 7:
        x = (161 * (position - 4)) + 300 + (161 / 2)
        y = 210
    elif position == 7:
        x = (161 / 2)
        y = 440 - 175
    elif 7 < position < 10:
        x = (161 * (position - 8))
        y = 440
    elif position == 10:
        x = 900
        y = 440
    elif position == 11:
        x = 1090
        y = 440
    else:
        x = 0
        y = 0
    return x, y


att_loc = (26, 181)
health_loc = (137, 181)


def update_card_stats(graph: sg.Graph, playerid: str, slot: int, health: str, attack: str):
    card_location = get_image_location(slot)
    att_center = tuple(map(operator.add, att_loc, card_location))
    health_center = tuple(map(operator.add, health_loc, card_location))
    # att_circle_center = tuple(map(operator.sub, att_center, (21, 18)))
    # health_circle_center = tuple(map(operator.sub, health_center, (21, 18)))
    slot_graph_ids = graph_ids[str(get_player_index(playerid))][str(slot)]
    if attack:
        if slot < 7:
            slot_graph_ids['attcirc'] = graph.draw_circle(att_center, 20, '#856515')
            # graph.draw_image("../assets/attack_orb.png", location=att_circle_center)
            slot_graph_ids['attval'] = graph.draw_text(str(attack), att_center, "white", "Arial 20")
    if health:
        if slot < 7 or slot == 11:
            slot_graph_ids['healthcirc'] = graph.draw_circle(health_center, 20, '#851717')
            # graph.draw_image("../assets/health_orb.png", location=health_circle_center)
            slot_graph_ids['healthval'] = graph.draw_text(str(health), health_center, "white", "Arial 20")


def draw_golden_overlay(graph: sg.Graph, position: (int, int)):
    pass
    # graph.draw_oval(position, tuple(map(operator.add, position, art_dim)), fill_color="gold")


def update_card(window: sg.Window, playerid: str, slot, cardname: str, content_id: str, health: str, attack: str,
                is_golden: bool):
    index = get_player_index(playerid)
    if index >= 0:
        graph = window[get_graph_key(index)]
        card_loc = get_image_location(int(slot))
        path = asset_utils.get_card_path(cardname, content_id, is_golden)
        slot_graph_ids = graph_ids[str(index)][str(slot)]
        if "Empty" in path and slot_graph_ids:
            for graph_id in slot_graph_ids.values():
                graph.delete_figure(graph_id)
        id = graph.draw_image(filename=path, location=card_loc)
        slot_graph_ids['card'] = id
        if is_golden:
            draw_golden_overlay(graph, card_loc)
        update_card_stats(graph, playerid, int(slot), health, attack)


def get_player_index(player_id: str):
    if player_id not in player_ids:
        player_ids.append(player_id)
    return player_ids.index(player_id)


def construct_layout():
    player_tabs = []
    for num in range(0, 8):
        name = "Player" + str(num)
        player_tabs.append(sg.Tab(layout=[[sg.Graph(canvas_size=(1350, 800), graph_bottom_left=(0, 800),
                                                    graph_top_right=(1350, 0),
                                                    key=get_graph_key(num))]],
                                  title=name, k=get_tab_key(num)))

    player_tab_group = [[sg.TabGroup(layout=[player_tabs])]]

    data = [['' for row in range(5)] for col in range(len(asset_utils.hero_ids))]
    headings = stats.headings
    starting_stats = sg.Table(values=data, headings=headings,
                              justification='center',
                              key='-StartingHeroStats-',
                              expand_y=True,
                              auto_size_columns=False,
                              vertical_scroll_only=True,
                              col_widths=[19, 10, 10, 10, 10])

    ending_stats = sg.Table(values=data, headings=headings,
                            justification='center',
                            key='-EndingHeroStats-',
                            expand_y=True,
                            auto_size_columns=False,
                            vertical_scroll_only=True,
                            col_widths=[19, 10, 10, 10, 10])

    hero_stats_tab = sg.TabGroup(layout=[[
        sg.Tab(layout=[[
            starting_stats
        ]], title="Starting Hero Stats"),
        sg.Tab(layout=[[
            ending_stats
        ]], title="Ending Hero Stats")
    ]], expand_y=True)

    application_tab_group = [[sg.TabGroup(layout=[[
        sg.Tab(layout=player_tab_group, title="In-Game"),
        sg.Tab(layout=[[sg.Col(layout=
                               [[sg.Frame(layout=[[]], key="-StartingHero-", size=(150, 800), title="Starting Hero"),
                                 sg.Frame(layout=[[]], key="-EndingHero-", size=(150, 800), title="Ending Hero"),
                                 sg.Frame(layout=[[]], key="-Placement-", size=(150, 800), title="Placement")]],
                               size=(150 * 3, 800), scrollable=True, vertical_scroll_only=True), hero_stats_tab]],
               title="Match History")
    ]])]]

    layout = [[sg.Menu([['&File', ['&Export Stats']], ['&Help']])],
              [sg.Text(text="Waiting for match to start...", font="Courier 32", k="-GameStatus-",
                       justification='center')], application_tab_group]

    return layout


def the_gui():
    """
    Starts and executes the GUI
    Reads data from a Queue and displays the data to the window
    Returns when the user exits / closes the window
    """
    sg.theme('Dark Blue 14')

    window = sg.Window('SBBTracker', construct_layout(), resizable=True, finalize=True, size=(1350, 800),
                       icon=resource_path("assets/sbbt.ico"))
    threading.Thread(target=log_parser.run, args=(window,), daemon=True).start()
    threading.Thread(target=update_check.run, args=(window,), daemon=True).start()
    player_stats = PlayerStats(window)
    current_player = None

    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        if event == 'Export Stats':
            filename = sg.popup_get_file('Export stats to .csv', save_as=True, default_extension=".csv", no_window=True,
                                         file_types=(("Text CSV", ".csv"),),
                                         initial_folder=str(Path(os.environ['USERPROFILE']).joinpath("Documents")))
            player_stats.export(Path(filename))
        elif event == log_parser.JOB_NEWGAME:
            for player_id in player_ids:
                index = get_player_index(player_id)
                graph = window[get_graph_key(index)]
                graph.erase()

            player_ids.clear()
            current_player = None
            window["-GameStatus-"].update("Round: 0")
        elif event == log_parser.JOB_INITCURRENTPLAYER:
            current_player = values[event]
        elif event == log_parser.JOB_ROUNDINFO:
            window["-GameStatus-"].update(f"Round: {values[event][1].round}")
        elif event == log_parser.JOB_PLAYERINFO:
            updated_player = values[event]
            update_player(window, updated_player)
        elif event == log_parser.JOB_BOARDINFO:
            update_board(window, values[event])
        elif event == log_parser.JOB_ENDGAME:
            player = values[event]
            if player:
                player_stats.update_stats(asset_utils.get_card_art_name(current_player.heroid, current_player.heroname),
                                          asset_utils.get_card_art_name(player.heroid, player.heroname), player.place)
        elif event == "GITHUB-UPDATE":
            choice = sg.popup_yes_no("New version available!\nWould you like to go to the download page?")
            if choice == "Yes":
                webbrowser.open_new_tab('https://github.com/SBBTracker/SBBTracker/releases/latest')

    # if user exits the window, then close the window and exit the GUI func
    window.close()
    player_stats.save()


if __name__ == '__main__':
    the_gui()
    print('Exiting Program')
