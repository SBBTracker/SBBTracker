#!/usr/bin/python3
import operator
import os
import sys
import threading
import webbrowser
from collections import defaultdict
from enum import Enum
from pathlib import Path

import PySimpleGUI as sg
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator

import application_constants as app
import asset_utils
import log_parser
import stats
import update_check
from application_constants import Keys
from stats import PlayerStats

player_ids = []
board_indicies = []

art_dim = (161, 204)

default_bg_color = "#21273d"
sns.set_style("darkgrid", {"axes.facecolor": default_bg_color})

plt.rcParams.update({'text.color': "white",
                     'xtick.color': 'white',
                     'ytick.color': 'white',
                     'figure.facecolor': default_bg_color,
                     'axes.labelcolor': "white"})


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


graph_ids = {str(player): {str(slot.value): {} for slot in Slot} for player in range(0, 9)}
names_to_health = defaultdict(dict)
ids_to_heroes = {}


def draw_matplotlib_figure(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg


def delete_fig_agg(fig_agg):
    fig_agg.get_tk_widget().forget()
    plt.close('all')


def make_health_graph():
    fig, ax = plt.subplots()
    last_values = []
    for player in names_to_health.keys():
        x = []
        y = []
        for round_num in names_to_health[player]:
            x.append(round_num)
            y.append(names_to_health[player][round_num])
        ax.plot(x, y, label=ids_to_heroes[player])
        last_values.append((x[-1], y[-1]))
        ax.annotate(y[-1], (x[-1], y[-1]))
    ax.legend()
    ax.set_xlabel("Turn")
    ax.set_ylabel("Health")
    plt.axhline(y=0, color='w', linewidth=2.0)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    fig.set_size_inches(13.5, 18)
    handles, labels = ax.get_legend_handles_labels()
    healths = [health for (_, health) in last_values]
    # sort both labels and handles by labels
    _, labels, handles = zip(*sorted(zip(healths, labels, handles), key=lambda t: t[0], reverse=True))
    ax.legend(handles, labels)
    return plt.gcf()


def add_asset_id(graph: sg.Graph, player_id: str, slot: str, asset_type: str, new_id):
    slot_graph_ids = graph_ids[str(get_player_index(player_id))][slot]
    if asset_type in slot_graph_ids:
        graph.delete_figure(slot_graph_ids[asset_type])
    slot_graph_ids[asset_type] = new_id


def update_player(window: sg.Window, update: log_parser.Update, round_num: int):
    state = update.state
    index = get_player_index(state.playerid)
    player_tab = window[app.get_tab_key(index)]
    real_hero_name = asset_utils.get_card_art_name(state.heroid, state.heroname)
    title = f"{real_hero_name}" if state.health > 0 else f"{real_hero_name} *DEAD*"
    player_tab.update(title=title)
    update_card(window, state.playerid, 11, state.heroname, state.heroid, state.health, "", False)
    names_to_health[state.playerid][round_num] = state.health
    ids_to_heroes[state.playerid] = real_hero_name


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
    if attack:
        if slot < 7:
            add_asset_id(graph, playerid, str(slot), "attcirc", graph.draw_circle(att_center, 20, '#856515'))
            # graph.draw_image("../assets/attack_orb.png", location=att_circle_center)
            add_asset_id(graph, playerid, str(slot), 'attval',
                         graph.draw_text(str(attack), att_center, "white", "Arial 20"))
    if health:
        if slot < 7 or slot == 11:
            add_asset_id(graph, playerid, str(slot), 'healthcirc', graph.draw_circle(health_center, 20, '#851717'))
            # graph.draw_image("../assets/health_orb.png", location=health_circle_center)
            add_asset_id(graph, playerid, str(slot), 'healthval',
                         graph.draw_text(str(health), health_center, "white", "Arial 20"))


def draw_golden_overlay(graph: sg.Graph, position: (int, int)):
    return graph.draw_image(filename="../assets/golden_overlay.png", location=position)


def update_card(window: sg.Window, playerid: str, slot, cardname: str, content_id: str, health: str, attack: str,
                is_golden):
    index = get_player_index(playerid)
    if index >= 0:
        graph = window[app.get_graph_key(index)]
        card_loc = get_image_location(int(slot))
        actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
        path = asset_utils.get_card_path(cardname, content_id, actually_is_golden)
        card_id = graph.draw_image(filename=path, location=card_loc)
        slot_graph_ids = graph_ids[str(index)][str(slot)]
        if "Empty" in path and slot_graph_ids:
            for graph_id in slot_graph_ids.values():
                graph.delete_figure(graph_id)
        add_asset_id(graph, playerid, str(slot), "card", card_id)
        if actually_is_golden:
            add_asset_id(graph, playerid, str(slot), 'golden', draw_golden_overlay(graph, card_loc))
        update_card_stats(graph, playerid, int(slot), health, attack)


def get_player_index(player_id: str):
    if player_id not in player_ids:
        player_ids.append(player_id)
    return player_ids.index(player_id)


def construct_layout():
    player_tabs = []
    for num in range(0, 8):
        name = "Player" + str(num)
        player_tabs.append(sg.Tab(layout=[
            [sg.Text("Last seen round: 0", font="Arial 18", key=app.get_player_round_key(num))],
            [sg.Graph(canvas_size=(1350, 800), graph_bottom_left=(0, 800),
                      graph_top_right=(1350, 0),
                      key=app.get_graph_key(num))]],
            title=name, k=app.get_tab_key(num)))

    player_tab_group = [[sg.TabGroup(layout=[player_tabs])]]

    data = [['' for __ in range(5)] for _ in range(len(asset_utils.hero_ids))]
    headings = stats.headings
    starting_stats = sg.Table(values=data, headings=headings,
                              justification='center',
                              key=Keys.StartingHeroStats.value,
                              expand_y=True,
                              auto_size_columns=False,
                              hide_vertical_scroll=True,
                              col_widths=[19, 10, 10, 10, 10])

    ending_stats = sg.Table(values=data, headings=headings,
                            justification='center',
                            key=Keys.EndingHeroStats.value,
                            expand_y=True,
                            auto_size_columns=False,
                            hide_vertical_scroll=True,
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
        sg.Tab(layout=player_tab_group, title="Board Comps"),
        sg.Tab(layout=[[sg.Canvas(key=Keys.HealthGraph.value)]], title="Health Graph"),
        sg.Tab(layout=[[sg.Col(layout=[[sg.Table(values=[['' for __ in range(3)] for _ in range(40)],
                                                 headings=["Starting Hero", "Ending Hero", "Placement"],
                                                 key=Keys.MatchStats.value, hide_vertical_scroll=True,
                                                 justification="Center", expand_y=True,
                                                 col_widths=[19, 19, 10], auto_size_columns=False)],
                                       [sg.Button("Prev"), sg.Text("Page: 1", key=Keys.StatsPageNum.value),
                                        sg.Button("Next")]],
                               expand_y=True, element_justification="center"),
                        hero_stats_tab]],
               title="Match History")
    ]])]]

    layout = [[sg.Menu([['&File', ['&Export Stats', '&Delete Stats']], ['&Help', ['&Report an issue']]])],
              [sg.Text(text="Waiting for match to start...", font="Arial 28", k=Keys.GameStatus.value,
                       justification='center')], application_tab_group]

    return layout


def the_gui():
    """
    Starts and executes the GUI
    Reads data from a Queue and displays the data to the window
    Returns when the user exits / closes the window
    """
    sg.theme('Dark Blue 14')
    sg.set_options(font="Arial 11")

    window = sg.Window('SBBTracker', construct_layout(), resizable=True, finalize=True, size=(1350, 820),
                       icon=resource_path("assets/sbbt.ico"))
    threading.Thread(target=log_parser.run, args=(window,), daemon=True).start()
    threading.Thread(target=update_check.run, args=(window,), daemon=True).start()
    player_stats = PlayerStats(window)
    current_player = None
    health_fig_agg = None
    round_number = 0
    page_number = 1

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

        elif event == 'Delete Stats':
            choice = sg.popup_yes_no("This will remove ALL of your stats? Are you sure?")
            if choice == "Yes":
                player_stats.delete()
        elif event == 'Report an issue':
            webbrowser.open_new_tab('https://github.com/SBBTracker/SBBTracker/issues')
        elif event == log_parser.JOB_NEWGAME:
            for player_id in player_ids:
                index = get_player_index(player_id)
                graph = window[app.get_graph_key(index)]
                window[app.get_player_round_key(index)].update(f"Last seen round: 0")
                graph.erase()

            player_ids.clear()
            names_to_health.clear()
            ids_to_heroes.clear()
            current_player = None
            round_number = 0
            window[Keys.GameStatus.value].update("Round: 0")
        elif event == log_parser.JOB_INITCURRENTPLAYER:
            current_player = values[event]
        elif event == log_parser.JOB_ROUNDINFO:
            round_number = values[event][1].round
            window[Keys.GameStatus.value].update(f"Round: {round_number}")
        elif event == log_parser.JOB_PLAYERINFO:
            updated_player = values[event]
            update_player(window, updated_player, round_number)
        elif event == log_parser.JOB_BOARDINFO:
            update_board(window, values[event])
            for player_id in values[event].state:
                index = get_player_index(player_id)
                window[app.get_player_round_key(index)].update(f"Last seen round: {round_number}")
        elif event == log_parser.JOB_ENDCOMBAT:
            if health_fig_agg is not None:
                delete_fig_agg(health_fig_agg)
            health_fig_agg = draw_matplotlib_figure(window[Keys.HealthGraph.value].TKCanvas, make_health_graph())
            window.refresh()
        elif event == log_parser.JOB_ENDGAME:
            player = values[event]
            if player:
                place = player.place if int(player.health) >= 0 else "1"
                player_stats.update_stats(asset_utils.get_card_art_name(current_player.heroid, current_player.heroname),
                                          asset_utils.get_card_art_name(player.heroid, player.heroname), place)
        elif event == "GITHUB-UPDATE":
            choice = sg.popup_yes_no("New version available!\nWould you like to go to the download page?")
            if choice == "Yes":
                webbrowser.open_new_tab('https://github.com/SBBTracker/SBBTracker/releases/latest')

        elif event == "Prev":
            if page_number > 1:
                page_number -= 1
            player_stats.update_page(page_number)
        elif event == "Next":
            if page_number < stats.get_num_pages(player_stats.df):
                page_number += 1
            player_stats.update_page(page_number)
    # if user exits the window, then close the window and exit the GUI func
    window.close()
    player_stats.save()


if __name__ == '__main__':
    the_gui()
    print('Exiting Program')
