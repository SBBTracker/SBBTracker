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
JOB_INITCURRENTPLAYER = "InitCurrentPlayer"
JOB_BOARDINFO = "BoardInfo"
JOB_ROUNDINFO = "RoundInfo"
JOB_NEWGAME = "StateNewgame"
JOB_ENDGAME = "StateEndGame"
JOB_ENDCOMBAT = "EndCombat"
JOB_HEALTHUPDATE = "HealthUpdate"
JOB_MATCHMAKING = "StateMatchmaking"
JOB_CARDUPDATE = "CardUpdate"
JOB_HERODISCOVER = "HeroDiscover"


def process_line(line, ifs):
    dt = {}

    line_data = line.split(' ')
    event = line_data[0].lstrip('[').rstrip(']')
    dt['event'] = event
    if event == EVENT_CONNINFO:
        session_id = line_data[1].split(':')[1]
        build_id = line_data[2].split(':')[1]
        return {**dt, **{'build_id': build_id, 'session_id': session_id}}
    elif event in [EVENT_ADDPLAYER, EVENT_ENTERRESULTSPHASE]:
        part = line.split('>==')[1].split('\'==')
        lookupname = line.split(f"[{event}]")[1].split('<')[0]
        displayname = part[0].lstrip('\'')
        playerid = part[1].split(' ')[0]
        line_data = line.split('\'==')[1].split()

        health = line_data[1].split(':')[-1]
        experience = line_data[3].split(':')[-1]
        place = line_data[6].split(':')[-1]
        level = line_data[5].split(':')[-1]
        heroid = line_data[7].split('<')[0]
        current_player = "<U>" in line

        dt = {**dt, **{'lookupname':lookupname, 'displayname': displayname, 'playerid': playerid, 'experience': experience, 'health': health,
                       'place': place, 'level': level, 'heroid': heroid, 'current_player':current_player}}
        if event == EVENT_ENTERRESULTSPHASE:
            for line_datum in line_data:
                if 'Rank' in line_datum:
                    mmr = line_datum.split(':')[-1]
                    dt = {**dt, **{'mmr': mmr}}
                    break
        return dt
    elif event == EVENT_ENTERBRAWLPHASE:
        parts = line.split('==\'')
        player1id = line.split(f"[{event}]")[1].split('<')[0] #   ] raschy    <U>
        player2id = line.split(f"-->")[1].split('<')[0] # --> raschy    <x>
        dt = {**dt, **{'player1id': player1id, 'player2id': player2id}}
        return dt
    elif event == EVENT_ENTERSHOPPHASE:
        for part in line_data:
            if part.startswith('Round:'):
                r = part.split(':')[1]
        return {**dt, 'round': r}

    elif event in [EVENT_CREATECARD, EVENT_UPDATECARD]:
        if '>:Shop[' in line or 'UNKNOWN' in line:
            return

        is_golden = False
        counter = None
        content_id = line_data[1].split('<')[0]

        linestart = []
        works = None
        for e, v in enumerate(line_data):
            if '/' in v:
                if len(v.split("/")) == 2:
                    works = True
                    try:
                        x = v.split("(")[0].split("/")
                        int(x[0])
                        int(x[1])
                    except ValueError:
                        works = False
                    if works:
                        break

        if not works:
            if '>:Spell[' in line:
                e = len(line_data) - 1

        linestart = ' '.join(line_data[2:e])
        line_data = [linestart, *line_data[e:]]
        playerlookup = line.split(">")[1].split('<')[0]
        cost = 0
        subtypes = []
        if '>:Treasure[' in line:
            slot = line.split('>:Treasure[')[1].split(']')[0]
            zone = 'Treasure'
        if '>:Spell[' in line or '>:NONE[' in line:
            slot = line.split('>:Spell[')[1].rstrip(']') if '>:Spell[' in line else line.split('>:NONE[')[1].rstrip(']')
            zone = 'Spell'
        else:
            zone = line_data[0].split(':')[1].split('[')[0]
            slot = line_data[0].split('[')[1].split(']')[0]
        if '>:Spell[' in line or '>:Treasure[' in line or '>:NONE[' in line:
            cardattack = 0
            cardhealth = 0
        else:
            try:
                cardattack = line_data[1].split('/')[0]
                cardhealth = line_data[1].split('/')[1]
            except IndexError:
                return

            subtypes = [i.lower() for i in line_data[2].split(':')[1].split(',')]
            for line_datum in line_data:
                if 'Cost' in line_datum:
                    cost = line_datum.split(':')[1]
                    break
        if len(line_data) > 4:
            for d in line_data:
                if d.startswith('Flag'):
                    is_golden = 'G' in d.split(':')[1]
                elif d.startswith('Counter'):
                    counter = d.split(':')[1]

        dt = {**dt, **{'is_golden': is_golden, 'counter': counter, 'content_id': content_id, 'playerlookup': playerlookup,
                       'zone': zone, 'slot': slot, 'cardattack': cardattack, 'cardhealth': cardhealth,
                       'subtypes': subtypes, 'cost': cost}}

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
            line = ' '.join(line.split()[2:])
            info = process_line(line, ifs)
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
                self.playerid = info.get("lookupname", "")
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
            #                self.choices = info['Choices']
            #                self.attrs = ['choices']

            elif self.action_type == EVENT_ENTERBRAWLPHASE:
                self.task = TASK_GATHERIDS
                self.player1 = info['player1id']
                self.player2 = info['player2id']
                self.attrs = ['player1', 'player2']

            elif self.action_type == EVENT_CREATECARD or self.action_type == EVENT_UPDATECARD:
                self.task = TASK_GETROUNDGATHER if self.action_type == EVENT_CREATECARD else TASK_UPDATECARD
                cardinfo = info

                self.playerid = cardinfo['playerlookup']
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
    while True:
        prev_action = None
        ifs = SBBPygtail(filename=str(log), offset_file=offsetfile, every_n=100)
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
                        # if action.playerid.startswith('[Action'):
                        #     playerlookup = ' '.join(action.playerid.split(' ')[2:])
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

