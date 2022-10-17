import sys
import gzip
import json
import os
import re
import time
from collections import defaultdict
from enum import Enum
from os.path import exists
from queue import Queue

from pygtail import Pygtail
from sbbtracker.paths import logfile, offsetfile

import logging

logger = logging.getLogger(__name__)

VERYLARGE = 2 ** 20
NOTFOUND = -1

EVENT_CHARACTER = 'Character'
EVENT_ADDPLAYER = 'ActionAddPlayer'
EVENT_ATTACK = 'ActionAttack'
EVENT_BRAWLCOMPLETE = 'ActionBrawlComplete'
EVENT_CASTSPELL = 'ActionCastSpell'
EVENT_CONNINFO = 'ActionConnectionInfo'
EVENT_CREATECARD = 'ActionCreateCard'
EVENT_DEALDAMAGE = 'ActionDealDamage'
EVENT_DEATH = 'ActionDeath'
EVENT_DEATHTRIGGER = 'ActionDeathTrigger'
EVENT_ENTERBRAWLPHASE = 'ActionEnterBrawlPhase'
EVENT_ENTERINTROPHASE = 'ActionEnterIntroPhase'
EVENT_ENTERRESULTSPHASE = 'ActionEnterResultsPhase'
EVENT_ENTERSHOPPHASE = 'ActionEnterShopPhase'
EVENT_MODIFYGOLD = 'ActionModifyGold'
EVENT_MODIFYLEVEL = 'ActionModifyLevel'
EVENT_MODIFYNEXTLEVELXP = 'ActionModifyNextLevelXP'
EVENT_MODIFYXP = 'ActionModifyXP'
EVENT_MOVECARD = 'ActionMoveCard'
EVENT_PLAYFX = 'ActionPlayFX'
EVENT_PRESENTDISCOVER = 'ActionPresentDiscover'
EVENT_PRESENTHERODISCOVER = 'ActionPresentHeroDiscover'
EVENT_REMOVECARD = 'ActionRemoveCard'
EVENT_ROLL = 'ActionRoll'
EVENT_SLAYTRIGGER = 'ActionSlayTrigger'
EVENT_SUMMONCHARACTER = 'ActionSummonCharacter'
EVENT_UPDATECARD = 'ActionUpdateCard'
EVENT_UPDATEEMOTES = 'ActionUpdateEmotes'
EVENT_UPDATETURNTIMER = 'ActionUpdateTurnTimer'
EVENT_SPELL = 'Spell'

TASK_ADDPLAYER = "AddPlayer"
TASK_UPDATECARD = "UpdateCard"
TASK_GATHERIDS = "GatherIDs"
TASK_GETROUND = "GetRound"
TASK_GETROUNDGATHER = "GetRoundGather"
TASK_ENDROUNDGATHER = "EndRoundGather"
TASK_NEWGAME = "TaskNewGame"
TASK_ENDGAME = "TaskEndGame"
TASK_ENDCOMBAT = "TaskEndCombat"
TASK_GETTHISPLAYER = "GetThisPlayer"
TASK_MATCHMAKING = "TaskMatchmaking"
TASK_HERODISCOVER = "TaskHeroDiscover"

JOB_PLAYERINFO = "PlayerInfo"
JOB_PLAYERINFODONE = "PlayerInfoDone"
JOB_BOARDINFO = "BoardInfo"
JOB_ROUNDINFO = "RoundInfo"
JOB_NEWGAME = "StateNewgame"
JOB_ENDGAME = "StateEndGame"
JOB_ENDCOMBAT = "EndCombat"
JOB_HEALTHUPDATE = "HealthUpdate"
JOB_MATCHMAKING = "StateMatchmaking"
JOB_CARDUPDATE = "CardUpdate"
JOB_HERODISCOVER = "HeroDiscover"


def process_line_wrapper(line, ifs):
    try:
        return process_line(line, ifs)
    except:
        logger.error(f'ERROR processing line: {line}')
        raise


def readuntil(string, substr, clean=True):
    """Find substr, chop off all before and including, and return everything afterwards"""
    find = string.find(substr)
    if find == -1:
        return string, ''

    cut = find + len(substr)
    car, cdr = string[:cut], string[cut:]
    if clean:
        car = car[:-1 * len(substr)]
    return car, cdr


def get_shortname(string):
    """ The logfile uses a truncated name system """
    shortname = string[:10]
    currentplayer = string[10:13] == '<U>'
    cdr = string[13:]
    logger.info(f'From line ||{string[:-1]}|| extracted shortname {shortname} currentplayer {currentplayer}')
    return shortname, currentplayer, cdr


def process_fullname(string):
    """ Process data of the format =='fullname'==0123456789012345 ' """
    # TODO what happens if a user has an apostrophe in their name
    displayname = ''
    _line = string[3:]
    annoyingstr = '\'=='
    while True:
        _displayname, _line = readuntil(_line, annoyingstr)
        displayname += _displayname
        linefind = _line.find(annoyingstr)
        if annoyingstr in _line and linefind < _line.find('Health:') and linefind < _line.find(
                'Gold:') and linefind < _line.find('NextLevelXP'):
            displayname += annoyingstr
        else:
            glg_id, _line = readuntil(_line, ' ')
            break

    logger.info(f'From line ||{string.strip()}|| extracted displayname {displayname} glg_id {glg_id}')
    return displayname, glg_id, _line


def process_line(line, ifs):
    dt = {}

    event, _line = readuntil(line, ' ')
    event = event.strip('[]')
    dt['event'] = event
    if event == EVENT_CONNINFO:
        line_data = line.split(' ')
        session_id = line_data[1].split(':')[1]
        build_id = line_data[2].split(':')[1]
        return {**dt, **{'build_id': build_id, 'session_id': session_id}}
    elif event in [EVENT_ADDPLAYER, EVENT_ENTERRESULTSPHASE]:
        playerid, current_player, _line = get_shortname(_line)
        displayname, glg_id, _line = process_fullname(_line)
        heroid = None
        while True:
            data, _line = readuntil(_line, ' ')
            if not data:
                break
            if heroid is None and '<' in data and '>' in data:
                heroid = data.split('<')[0]
            if not ':' in data:
                continue

            k, v = data.split(':')
            v = v.strip()
            if k == 'Health':
                health = v
            elif k == 'XP':
                experience = v
            elif k == 'Place':
                place = v
            elif k == 'Level':
                level = v
            elif k == 'Rank':  # This will only happen with ENTERRESULTSPHASE
                mmr = v

        dt = {**dt,
              **{'displayname': displayname, 'displayname': displayname, 'playerid': playerid, 'experience': experience,
                 'health': health,
                 'place': place, 'level': level, 'heroid': heroid, 'current_player': current_player, 'glg_id': glg_id}}
        if event == EVENT_ENTERRESULTSPHASE:
            dt = {**dt, **{'mmr': mmr}}

        return dt
    elif event == EVENT_ENTERBRAWLPHASE:
        player1id, _, _line = get_shortname(_line)
        _, _, _line = process_fullname(_line)
        junk, _line = readuntil(_line, '--> ')
        player2id, _, _line = get_shortname(_line)
        dt = {**dt, **{'player1id': player1id, 'player2id': player2id}}
        return dt
    elif event == EVENT_ENTERSHOPPHASE:
        _, _, _line = get_shortname(_line)
        _, _, _line = process_fullname(_line)
        _, _line = readuntil(_line, '--> ')
        _, _, _line = get_shortname(_line)
        while True:
            _line = _line.lstrip(' ')
            data, _line = readuntil(_line, ' ')
            if not data:
                break
            if not ':' in data:
                continue

            k, v = data.split(':')
            v = v.strip()
            if k == 'Round':
                r = v
                break  # this is the only thing we care about

        return {**dt, 'round': r}

    elif event in [EVENT_CREATECARD, EVENT_UPDATECARD]:

        is_golden = False
        counter = -1
        cardattack = None
        cardhealth = None
        subtypes = []

        content_data, _line = readuntil(_line, ' ')
        content_id = content_data.split('<')[0]

        playerid, currentplayer, _line = get_shortname(_line)

        _line = _line[1:]  # remove the leading :
        zoneinfo, _line = readuntil(_line, ' ', clean=False)
        zone, slotinfo = zoneinfo.split('[')
        slot = slotinfo[:-2]

        while True:
            _line = _line.lstrip(' ')
            data, _line = readuntil(_line, ' ')
            if not data:
                break
            if '/' in data and not ':' in data:
                try:
                    _cardattack, _cardhealth = map(str.strip, data.split('/'))
                    _cardattack = int(_cardattack)
                    _cardhealth = int(_cardhealth)
                    cardattack = _cardattack
                    cardhealth = _cardhealth
                except ValueError:
                    pass
            if not ':' in data:
                continue

            k, v = data.split(':')
            v = v.strip()
            if k == 'Subtypes':
                subtypes = list(map(str.lower, v.split(',')))
            elif k == 'Cost':
                cost = v
            elif k == 'Flags':
                is_golden = 'G' in v
            elif k == 'Counter':
                counter = v

        dt = {**dt, **{'is_golden': is_golden, 'counter': counter, 'content_id': content_id, 'playerid': playerid,
                       'zone': zone, 'slot': slot, 'cardattack': cardattack, 'cardhealth': cardhealth,
                       'subtypes': subtypes, 'cost': cost}}
        return dt

    elif event == EVENT_PRESENTHERODISCOVER:
        line_data = line.replace(', ', '  ').split(' ')
        choices = []
        for datum in line_data:
            if re.match('^.+<.+>$', datum):
                choices.append(datum.split('<')[0])

        dt = {**dt, **{ 'choices': choices }}

    return dt


def parse(ifs):
    """
    Parse the log file into workable dictionaries. A nice function to
    separate the business logic from the parsing logic

    Parameters
    ----------
    ifs : Input file stream
        The tail of the logfile being read in

    Yields
    ------
    info : Dictionary
        A log line, dynamically transformed into a dict object for
        further processing

    """
    for line in ifs:
        if 'REQUEST MATCHMAKER FOR' in line:
            game_mode = "SBB99" if "100P" in line else "Normal"
            yield Action(info=game_mode, game_state=GameState.MATCHMAKING)
        elif line.startswith('[RECV]'):
            _, line = readuntil(line, ' ')
            _, line = readuntil(line, ' ')
            info = process_line_wrapper(line, ifs)
            if info:
                yield Action(info)


class GameState(Enum):
    START = 1
    END = 2
    REAL_SHOP_PHASE = 3
    MATCHMAKING = 4
    UNKNOWN = 5


class Action:
    def __init__(self, info, game_state=GameState.UNKNOWN):
        if game_state == GameState.MATCHMAKING:
            self.task = TASK_MATCHMAKING
            self.game_mode = info
            self.attrs = ['task', 'game_mode']
            return

        if info is not None:

            self.action_type = info['event']
            if self.action_type == EVENT_ADDPLAYER or self.action_type == EVENT_ENTERRESULTSPHASE:
                self.task = TASK_ADDPLAYER
                self.displayname = info['displayname'].strip()
                self.heroid = info['heroid']
                self.health = int(info['health'])
                self.playerid = info.get("playerid", "")
                self.place = info['place']
                self.experience = info['experience']
                self.level = info['level']
                self.current_player = info["current_player"]
                self.attrs = ['displayname', 'playerid', 'health', 'heroid', 'place', 'level', 'experience']

                if self.action_type == EVENT_ENTERRESULTSPHASE:
                    self.task = TASK_ENDGAME
                    self.mmr = info['mmr']
                    self.attrs.append('mmr')

            elif self.action_type == EVENT_PRESENTHERODISCOVER:
                # TODO broken on glg side
                self.attrs = []
                self.task = TASK_HERODISCOVER
                self.choices = info['choices']
                self.attrs = ['choices']

            elif self.action_type == EVENT_ENTERBRAWLPHASE:
                self.task = TASK_GATHERIDS
                self.player1 = info['player1id']
                self.player2 = info['player2id']
                self.attrs = ['player1', 'player2']

            elif self.action_type in [EVENT_CREATECARD, EVENT_UPDATECARD]:
                self.task = TASK_GETROUNDGATHER if self.action_type == EVENT_CREATECARD else TASK_UPDATECARD
                cardinfo = info

                self.playerid = cardinfo['playerid']
                self.cardattack = cardinfo['cardattack']
                self.cardhealth = cardinfo['cardhealth']
                self.is_golden = cardinfo['is_golden']
                self.slot = cardinfo['slot']
                self.zone = cardinfo['zone']
                self.cost = cardinfo['cost']
                self.subtypes = cardinfo['subtypes']
                self.counter = cardinfo['counter']

                self.content_id = info['content_id']
                self.attrs = ['cardattack', 'cardhealth', 'is_golden', 'slot', 'zone', 'cost', 'subtypes', 'counter',
                              'content_id']

            elif self.action_type in [EVENT_BRAWLCOMPLETE, EVENT_SUMMONCHARACTER, EVENT_ATTACK, EVENT_DEALDAMAGE]:
                self.task = TASK_ENDROUNDGATHER
                self.attrs = []

            elif self.action_type == EVENT_ENTERSHOPPHASE:
                self.task = TASK_GETROUND
                self.round_num = int(info['round'])
                self.attrs = ['round_num']

            elif self.action_type == EVENT_UPDATETURNTIMER:
                self.task = TASK_ENDCOMBAT
                self.attrs = []

            elif self.action_type == EVENT_CONNINFO:
                self.task = TASK_NEWGAME
                self.session_id = info['session_id']
                self.build_id = info['build_id']
                self.attrs = ['session_id', 'build_id']

            else:
                self.task = None
                self.attrs = []

            self.attrs.append("action_type")

    def __repr__(self):
        return json.dumps({k: getattr(self, k) for k in ['task', *self.attrs]}, sort_keys=True, indent=4)


class Update:
    def __init__(self, job, state):
        self.job = job
        self.state = state


class SBBPygtail(Pygtail):
    def _check_rotated_filename_candidates(self):
        return self.filename

    def _filehandle(self):
        """
        Return a filehandle to the file being tailed, with the position set
        to the current offset.
        """
        if not self._fh or self._is_closed():
            filename = self._rotated_logfile or self.filename
            if filename.endswith('.gz'):
                self._fh = gzip.open(filename, 'r', encoding="utf-8")
            else:
                self._fh = open(filename, "r", 1, encoding="utf-8")
            if self.read_from_end and not exists(self._offset_file):
                self._fh.seek(0, os.SEEK_END)
            else:
                self._fh.seek(self._offset)

        return self._fh


def run(queue: Queue, log=logfile):
    inbrawl = False
    current_round = None
    lastupdated = dict()
    prev_action = None
    while True:
        ifs = SBBPygtail(filename=str(log), offset_file=offsetfile, every_n=100, full_lines=True)
        for action in parse(ifs):
            if action.task == TASK_NEWGAME:
                inbrawl = False
                current_round = None
                lastupdated = dict()
                queue.put(Update(JOB_NEWGAME, action))
            elif action.task == TASK_ENDGAME:
                queue.put(Update(JOB_ENDGAME, action))
            else:
                if action.task == TASK_HERODISCOVER:
                    queue.put(Update(JOB_HERODISCOVER, action))
                elif action.task == TASK_ADDPLAYER and prev_action is not None \
                        and (prev_action.action_type not in [EVENT_ENTERRESULTSPHASE, EVENT_ADDPLAYER,
                                                             EVENT_UPDATETURNTIMER]):
                    queue.put(Update(JOB_HEALTHUPDATE, action))
                elif not inbrawl and action.task == TASK_ADDPLAYER:
                    queue.put(Update(JOB_PLAYERINFO, action))
                elif not inbrawl and action.task == TASK_GATHERIDS:
                    inbrawl = True
                    brawldt = dict()
                    character_slots = defaultdict(set)
                    brawldt[action.player1] = list()
                    brawldt[action.player2] = list()
                    lastupdated[action.player1] = current_round
                    lastupdated[action.player2] = current_round
                elif inbrawl and action.task == TASK_GETROUNDGATHER:
                    if action.zone == 'Char':
                        if action.slot not in character_slots[action.playerid]:
                            character_slots[action.playerid].add(action.slot)
                            brawldt[action.playerid].append(action)
                    else:
                        playerid = action.playerid
                        try:
                            brawldt[playerid].append(action)
                        except KeyError:
                            print(brawldt.keys(), playerid, action)
                elif inbrawl and action.task != TASK_GETROUNDGATHER:
                    queue.put(Update(JOB_BOARDINFO, brawldt))
                    inbrawl = False
                elif action.task == TASK_GETROUND:
                    queue.put(Update(JOB_ROUNDINFO, action))
                elif action.task == TASK_ENDCOMBAT:
                    queue.put(Update(JOB_ENDCOMBAT, action))
                elif action.task == TASK_MATCHMAKING:
                    queue.put(Update(JOB_MATCHMAKING, action))
                elif not inbrawl and action.task == TASK_UPDATECARD:
                    queue.put(Update(JOB_CARDUPDATE, action))
                else:
                    pass

            prev_action = action
        time.sleep(0.01)


queue = Queue()