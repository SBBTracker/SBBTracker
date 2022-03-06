import gzip
import json
import os
import time
from collections import defaultdict
from enum import Enum
from os.path import exists
from queue import Queue

from pygtail import Pygtail
from sbbtracker.paths import logfile, offsetfile

from sbbtracker.utils.asset_utils import reverse_template_id


VERYLARGE = 2 ** 20
NOTFOUND = -1

EVENT_CHARACTER = 'Character'
EVENT_ADDPLAYER = 'GLG.Transport.Actions.ActionAddPlayer'
EVENT_ATTACK = 'GLG.Transport.Actions.ActionAttack'
EVENT_BRAWLCOMPLETE = 'GLG.Transport.Actions.ActionBrawlComplete'
EVENT_CASTSPELL = 'GLG.Transport.Actions.ActionCastSpell'
EVENT_CONNINFO = 'GLG.Transport.Actions.ActionConnectionInfo'
EVENT_CREATECARD = 'GLG.Transport.Actions.ActionCreateCard'
EVENT_DEALDAMAGE = 'GLG.Transport.Actions.ActionDealDamage'
EVENT_DEATH = 'GLG.Transport.Actions.ActionDeath'
EVENT_DEATHTRIGGER = 'GLG.Transport.Actions.ActionDeathTrigger'
EVENT_ENTERBRAWLPHASE = 'GLG.Transport.Actions.ActionEnterBrawlPhase'
EVENT_ENTERINTROPHASE = 'GLG.Transport.Actions.ActionEnterIntroPhase'
EVENT_ENTERRESULTSPHASE = 'GLG.Transport.Actions.ActionEnterResultsPhase'
EVENT_ENTERSHOPPHASE = 'GLG.Transport.Actions.ActionEnterShopPhase'
EVENT_MODIFYGOLD = 'GLG.Transport.Actions.ActionModifyGold'
EVENT_MODIFYLEVEL = 'GLG.Transport.Actions.ActionModifyLevel'
EVENT_MODIFYNEXTLEVELXP = 'GLG.Transport.Actions.ActionModifyNextLevelXP'
EVENT_MODIFYXP = 'GLG.Transport.Actions.ActionModifyXP'
EVENT_MOVECARD = 'GLG.Transport.Actions.ActionMoveCard'
EVENT_PLAYFX = 'GLG.Transport.Actions.ActionPlayFX'
EVENT_PRESENTDISCOVER = 'GLG.Transport.Actions.ActionPresentDiscover'
EVENT_PRESENTHERODISCOVER = 'GLG.Transport.Actions.ActionPresentHeroDiscover'
EVENT_REMOVECARD = 'GLG.Transport.Actions.ActionRemoveCard'
EVENT_ROLL = 'GLG.Transport.Actions.ActionRoll'
EVENT_SLAYTRIGGER = 'GLG.Transport.Actions.ActionSlayTrigger'
EVENT_SUMMONCHARACTER = 'GLG.Transport.Actions.ActionSummonCharacter'
EVENT_UPDATECARD = 'GLG.Transport.Actions.ActionUpdateCard'
EVENT_UPDATEEMOTES = 'GLG.Transport.Actions.ActionUpdateEmotes'
EVENT_UPDATETURNTIMER = 'GLG.Transport.Actions.ActionUpdateTurnTimer'
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


def parse_list(line, delimiter):
    """
    Transforms weird delimited sections of logfile into nice lists.
    Can also be used to operate on badly formatted section of log that
    are missing their pipes.

    Parameters
    ----------
    line : str
        The current line of text being operated on
    delimiter : str
        The delimiter we're expecting to see in the
        line separating list elements

    Returns
    -------
    specval : list(str)
        A list of values derived from the line
    new_line : TYPE
        The line, shortened after the point of the list

    """
    find = ':'
    dis = line.find(find)
    if dis == -1:
        dis = len(line)
    reverb = ''.join(reversed(line[:dis]))
    lastpipe = reverb.find(delimiter)
    items = line[:dis][:-lastpipe].split(delimiter)
    specval = [i.strip() for i in items]

    new_line = line[dis - lastpipe:].strip()

    return new_line, specval


def process_line(line, ifs, dt=None, path=[]):
    """
    A fun recursive function for turning a log line into a dictionary.
    Log lines are kind of like flattened YAML, except they have mistakes
    and have random newlines inside of them and are all around
    a fantastic time. We handle those edge cases here.

    Parameters
    ----------
    line : str
        The current line of text being operated on
    ifs : input file stream
        We need this when we find aberrant newlines...
    dt : dict
        This is where the state of the dictionary is being held. Exists
        to be passed through the recursive function
    path : list(str)
        The ordered set of keys that bring us to our current "locatiom" in
        the dict. There may be a better way to do this, I don't know
    """
    specval = None
    brick = None

    current_key = None if not path else path[-1]  # last item of path if exists

    # State dictionary invocation
    if dt is None:
        lb_dt = lambda: defaultdict(lb_dt)
        dt = defaultdict(lb_dt)

    # Get to the correct depth of the dictionary for state
    _dt = dt
    for p in path[:len(path) - 1]:
        _dt = _dt[p]

        # If we're handling a list gather it here
    if current_key in ['Keywords', 'Subtypes', 'ValidTargets']:
        line, specval = parse_list(line=line, delimiter='|')
        specval = specval[:-2]
    # If we need to hunt for the next val do it here
    elif current_key in ['FrameOverride']:
        line, specval = parse_list(line=line, delimiter=' ')
    else:
        # First find the distance to the first colon or pipe
        # colon means we go "in" a level
        # pipe means we go "up" a level
        coldis = line.find(':')
        pipedis = line.find('|')

        if current_key == 'GameText' or current_key == 'DisplayName':
            coldis = VERYLARGE
            # I hope to god this code never does anything
            healthstr = '| Health:'
            if current_key == 'DisplayName' and line.find(healthstr) != line.rfind(healthstr):
                instances = []
                cpy = line
                while cpy.find(healthstr) != -1:
                    loc = cpy.find(healthstr)
                    instances.append(loc + len(instances) * len(healthstr))
                    cpy = cpy.replace(healthstr, '', 1)

                pipedis = instances[-2]

        # Handle game text having newlines
        # By grabbing the next line and attaching it if we
        # Can't find a colon OR a pipe
        if coldis in [NOTFOUND, VERYLARGE] and pipedis in [NOTFOUND]:
            if current_key == 'GameText':
                line = line + ifs.next()
                coldis = VERYLARGE
                pipedis = line.find('|')

        # Make sure -1s are handled appropriately for minmath
        if coldis == NOTFOUND:
            coldis = VERYLARGE
        if pipedis == NOTFOUND:
            pipedis = VERYLARGE

    if specval is not None:
        val = specval
    else:
        chop = min(coldis, pipedis)
        brick = line[:chop].strip()
        line = line[chop + 1:]
        val = brick

    if specval is None and pipedis == coldis:
        if path and val:
            _dt[current_key] = val

        return dt
    if specval is not None or pipedis < coldis:
        # If we have a special value, then add it to the value
        # of the current key. If we've found a pipe before a colon
        # then we also have a value to record.
        if val:
            _dt[current_key] = val

        else:
            # Frame overrides can have no discernible value sometimes
            if current_key == 'FrameOverride':
                _dt[current_key] = val

        path = path[:-1]
        process_line(line, ifs, dt, path)
    else:
        # we've found a colon, we must go deeper
        process_line(line, ifs, dt, [*path, brick])

    # base case
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
            yield Action(info=None, game_state=GameState.MATCHMAKING)
        elif 'Writing binary data to recorder for action:' in line:
            chop_idx = line.find('-') + 1
            line = line[chop_idx:]
            info = process_line(line, ifs)

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
            return

        if info is not None:

            self.action_type = info['Action']['Type']
            if self.action_type == EVENT_ADDPLAYER or self.action_type == EVENT_ENTERRESULTSPHASE:
                self.task = TASK_ADDPLAYER
                self.displayname = info['DisplayName']
                self.heroid = info['Hero']['Card']['CardTemplateId']
                self.health = int(info['Health'])
                self.playerid = info.get("Player", "").replace("Id ", "")
                self.place = info['Place']
                self.experience = info['Experience']
                self.level = info['Level']
                self.attrs = ['displayname', 'playerid', 'health', 'heroid', 'place', 'level', 'experience']

                if self.action_type == EVENT_ENTERRESULTSPHASE:
                    self.task = TASK_ENDGAME
                    self.mmr = info['Hero']['Card']['RankReward']
                    self.playerid = info["PlayerData"].replace("Id ", "")
                    self.attrs.append('mmr')

            # elif self.action_type == EVENT_PRESENTHERODISCOVER:

            elif self.action_type == EVENT_ENTERBRAWLPHASE:
                self.task = TASK_GATHERIDS
                self.player1 = info['Action']['FirstPlayerId']
                self.player2 = info['Action']['SecondPlayerId']
                self.attrs = ['player1', 'player2']

            elif self.action_type == EVENT_CREATECARD or self.action_type == EVENT_UPDATECARD:
                self.task = TASK_GETROUNDGATHER if self.action_type == EVENT_CREATECARD else TASK_UPDATECARD
                cardinfo = info['Action']['Card']['[ClientCardCard]']['CardTemplate']['Card']['Delta']['[CardDelta]']

                self.playerid = cardinfo['PlayerId']
                self.cardattack = cardinfo['Attack']
                self.cardhealth = cardinfo['Health']
                self.is_golden = cardinfo['IsGolden']
                self.slot = cardinfo['Slot']
                self.zone = cardinfo['Zone']
                self.cost = cardinfo['Cost']
                self.subtypes = cardinfo['Subtypes']
                self.counter = cardinfo['Counter']

                self.content_id = info['Action']['Card']['[ClientCardCard]']['CardTemplate']['Card']['CardTemplateId']
                self.attrs = ['cardattack', 'cardhealth', 'is_golden', 'slot', 'zone', 'cost', 'subtypes', 'counter', 'content_id']

            elif self.action_type in [EVENT_BRAWLCOMPLETE, EVENT_SUMMONCHARACTER, EVENT_ATTACK, EVENT_DEALDAMAGE]:
                self.task = TASK_ENDROUNDGATHER
                self.attrs = []

            elif self.action_type == EVENT_ENTERSHOPPHASE:
                self.task = TASK_GETROUND
                self.round_num = int(info['Round'])
                self.attrs = ['round_num']

            elif self.action_type == EVENT_UPDATETURNTIMER:
                self.task = TASK_ENDCOMBAT
                self.attrs = []

            elif self.action_type == EVENT_CONNINFO:
                self.task = TASK_NEWGAME
                self.session_id = info['SessionId']
                self.build_id = info['BuildId']
                self.attrs = ['session_id', 'build_id']

            else:
                self.task = None
                self.attrs = []

            self.timestamp = info["Action"]["Timestamp"]
            self.attrs.append("timestamp")
            self.attrs.append("action_type")

    def __repr__(self):
        return json.dumps({k: getattr(self, k) for k in ['task', *self.attrs]}, sort_keys=True, indent=4)

    @classmethod
    def from_state(cls, state):
        card = cls(info=None)
        template_id = reverse_template_id(
            state['content_id'], golden=state.get("is_golden", False)
        )

        card.content_id = template_id
        card.zone = state['zone']
        card.task = ""
        card.action_type = "GLG.Transport.Actions.ActionCreateCard"
        card.counter = state.get('counter', '-1')
        card.playerid = state["playerid"]

        card.attrs = ["content_id", "zone", "task", "action_type", "counter", "playerid"]

        if state["zone"] == "Hero":
            card.displayname = ""
            card.health = 1 # player health is cast to an int
            card.heroid = template_id
            card.place = "-1"
            card.level = "-1"
            card.experience = "-1"
            card.slot = "0"
            card.attrs.extend(
                [
                    'displayname', 'health', 'heroid', 'place', 'level', 'experience', 'slot',
                ]
            )

        elif state["zone"] in ("Character", "Treasure", "Spell"):
            card.cardattack = str(state.get('cardattack', '0'))
            card.cardhealth = str(state.get('cardhealth', '0'))
            card.is_golden = state.get('is_golden', False)
            card.cost = str(state.get('cost', '-1')) # TODO see if this will always be there
            card.subtypes = state.get('subtypes', []) # TODO see if this will always be there
            card.slot = state.get('slot', '0')

            card.attrs.extend(
                [
                    'cardattack',
                    'cardhealth',
                    'is_golden',
                    'cost',
                    'subtypes',
                    'slot',
                ]
            )
        return card


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
    current_player_stats = None
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
            elif not inbrawl and not current_player_stats and action.task == TASK_ADDPLAYER \
                    and prev_action is not None and prev_action.action_type == EVENT_UPDATEEMOTES:
                current_player_stats = action
                queue.put(Update(JOB_INITCURRENTPLAYER, current_player_stats))
            elif action.task == TASK_ADDPLAYER and prev_action is not None \
                    and (prev_action.action_type not in [EVENT_ENTERRESULTSPHASE, EVENT_ADDPLAYER, EVENT_UPDATETURNTIMER]):
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
                if action.zone in ['Spell', 'Treasure', 'Character', 'Hero']:
                    if action.zone == 'Character':
                        if action.slot not in character_slots[action.playerid]:
                            character_slots[action.playerid].add(action.slot)
                            brawldt[action.playerid].append(action)
                    else:
                        brawldt[action.playerid].append(action)
            elif inbrawl and action.task != TASK_GETROUNDGATHER:
                queue.put(Update(JOB_BOARDINFO, brawldt))
                inbrawl = False
            elif action.task == TASK_GETROUND:
                queue.put(Update(JOB_ROUNDINFO, action))
            elif action.task == TASK_ENDGAME:
                queue.put(Update(JOB_ENDGAME, action))
                current_player_stats = None
            elif action.task == TASK_ENDCOMBAT:
                queue.put(Update(JOB_ENDCOMBAT, action))
            elif action.task == TASK_MATCHMAKING:
                queue.put(Update(JOB_MATCHMAKING, action))
            elif not inbrawl and action.task == TASK_UPDATECARD:
                queue.put(Update(JOB_CARDUPDATE, action))
            else:
                pass

            if action.task == TASK_ADDPLAYER:
                if current_player_stats and action.displayname == current_player_stats.displayname:
                    current_player_stats = action
            prev_action = action
        time.sleep(0.1)
