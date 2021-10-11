#!/usr/bin/python3
import os
import threading
import time
from pathlib import Path, PurePath

import PySimpleGUI as sg
import psutil

import LogParser
from player import Player, Card

player_ids = []


def simluate_sbb(window):
    i = 0
    time.sleep(4)
    fakePlayer = Player("Isik", "20", 6, "Celestial Tiger", {1: "Mimic", 2: "Merlin's Hat",
                                                             3: "Crystal Ball"},
                        {1: Card("Aon", 0, 0, False, 1), 2: Card("Aon", 0, 0, False, 2),
                         3: Card("Juliet", 0, 0, False, 3),
                         # 4: Card("Prince Arthur", 0, 0), 5: Card("Court Wizard", 0, 0),
                         6: Card("Court Wizard", 0, 0, False, 6), 7: Card("Romeo", 0, 0, False, 7)},
                        "", 40, 6)
    i += 1
    print("test")
    window.write_event_value('PLAYER UPDATE', fakePlayer)  # put a message into queue for GUI


def get_card_path(card_name: str, is_golden: bool):
    path = Path(__file__).parent.parent.joinpath("cards/")
    # what the fuck is this
    actually_is_golden = is_golden if isinstance(is_golden, bool) else is_golden == "True"
    if card_name == "empty":
        path = path.joinpath("Empty.png")
    elif card_name == "Triply":
        path = path.joinpath("Dubly upgraded.png")
    else:
        path = path.joinpath(card_name.replace("'", "_") + (" upgraded" if actually_is_golden else "") + ".png")
    return str(path)


def construct_player_layout(player: Player, index: int):
    ind = str(index)
    layout = [
        [sg.Image(get_card_path(player.get_minion(1).name, False), pad=((300, 0), 0), key=ind + "0"),
         sg.Image(get_card_path(player.get_minion(2).name, False), key=ind + "1"),
         sg.Image(get_card_path(player.get_minion(3).name, False), key=ind + "2"),
         sg.Image(get_card_path(player.get_minion(4).name, False), key=ind + "3")],
        [sg.Image(get_card_path(player.get_minion(5).name, False), pad=((400, 0), 0), key=ind + "4"),
         sg.Image(get_card_path(player.get_minion(6).name, False), key=ind + "5"),
         sg.Image(get_card_path(player.get_minion(7).name, False), key=ind + "6")],
        [sg.Image(get_card_path(player.get_treasure(1), False), key=ind + "7"),
         sg.Image(get_card_path(player.get_treasure(2), False), key=ind + "8"),
         sg.Image(get_card_path(player.get_treasure(3), False), pad=((0, 500), 0), key=ind + "9"),
         sg.Image(get_card_path(player.get_treasure(3), False), key=ind + "10"),
         sg.Image(get_card_path(player.hero if player.hero else "empty", False), key=ind + "11")]
    ]
    return layout


def get_tab_key(index: int):
    return f"-{index}-"


def update_player(window: sg.Window, update: LogParser.Update):
    state = update.state
    index = get_player_index(state.playerid)
    window[get_tab_key(index)].update(title=f"{state.displayname} - {state.heroname}")
    window[f"{index}{11}"].update(filename=get_card_path(state.heroname, False))


def update_board(window: sg.Window, update: LogParser.Update):
    for playerid, actions in update.state.items():
        for action in actions:
            slot = action.slot
            zone = action.zone
            position = 10 if zone == 'Spell' else (7 + int(slot)) if zone == "Treasure" else slot
            cardname = action.cardname
            update_card(window, playerid, position, cardname, action.is_golden)


def update_card(window: sg.Window, playerid: str, position, cardname: str, is_golden: bool):
    index = get_player_index(playerid)
    if index > 0:
        window[f"{index}{position}"].update(filename=get_card_path(cardname, is_golden))


def get_player_index(player_id: str):
    if player_id not in player_ids:
        player_ids.append(player_id)
    return player_ids.index(player_id) + 1


def the_gui():
    """
    Starts and executes the GUI
    Reads data from a Queue and displays the data to the window
    Returns when the user exits / closes the window
    """
    sg.theme('Dark Blue 14')

    tabs_layout = []
    for num in range(1, 9):
        name = "Player" + str(num)
        tabs_layout.append(sg.Tab(layout=construct_player_layout(Player(name=name, id="test", last_seen=0, hero="",
                                                                        treasures={}, minions={}, spell="", health=40,
                                                                        level=1), num), title=name,
                                  k=get_tab_key(num)))

    tabgroup = [[sg.TabGroup(layout=[tabs_layout])]]

    layout = [[sg.Text(text="Waiting for match to start...", font="Courier 32", k="-GameStatus-",
                       justification='center')], tabgroup]

    # layout = tabgroup

    window = sg.Window('SBBTracker', layout, resizable=True, finalize=True, size=(1920, 1080))
    # threading.Thread(target=simluate_sbb, args=(window,), daemon=True).start()
    threading.Thread(target=LogParser.run, args=(window,), daemon=True).start()
    # threading.Thread(target=poll_sbb_process, args=(window,), daemon=True).start()

    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'):
            break
        elif event == LogParser.JOB_NEWGAME:
            print("Game started!")
            for id in player_ids:
                for pos in range(11):
                    update_card(window, id, pos, "empty", False)
            player_ids.clear()
            window["-GameStatus-"].update("Round: 0")
        elif event == LogParser.JOB_ROUNDINFO:
            print("Round info event")
            window["-GameStatus-"].update(f"Round: {values[event][1].round}")
        elif event == LogParser.JOB_PLAYERINFO:
            print("Player info event")
            updated_player = values[event]
            update_player(window, updated_player)
        elif event == LogParser.JOB_BOARDINFO:
            print("Board info event")
            update_board(window, values[event])

    # if user exits the window, then close the window and exit the GUI func
    window.close()
    try:
        os.remove(LogParser.offsetfile)
    except:
        print("Couldn't delete offset!")


if __name__ == '__main__':
    the_gui()
    print('Exiting Program')
