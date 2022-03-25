from typing import BinaryIO
import re

import binascii
import struct
from construct import Struct, Const, Padding, PascalString, Int32ub, Int8ub, Int16ul, Int32ul, Int32sl, Int16ub, \
    Int64ul, PrefixedArray, Select, GreedyRange, Flag, Float32b, Float32l, Float32n, Sequence, Adapter, PaddedString, \
    Array, Byte, Probe, Enum, this

STRUCT_GUID = Struct(
    "field_1" / Int32ul,
    "field_2" / Int16ul,
    "field_3" / Int16ul,
    "field_4" / Int64ul
)

preamble_regex = re.compile(r"ClientVersion:\[([^\]]+)\]\|TransportVersion:\[([^\]]+)\]\|CardDatabaseVersion:\[([^\]]+)\]")


def parse_preamble(f: BinaryIO):
    preamble = f.readline().decode("utf-8")
    answer = preamble_regex.match(preamble)
    client_version = answer[1]
    transport_version = answer[2]
    card_database_version = answer[3]
    return client_version, transport_version, card_database_version


class GuidAdapter(Adapter):

    def _decode(self, obj, context, path):
        bytes = [struct.pack(">L", obj.field_1), struct.pack(">H", obj.field_2), struct.pack(">H", obj.field_3),
                 struct.pack("<Q", obj.field_4)]
        hexlified = [binascii.hexlify(x).decode("ascii") for x in bytes]
        return "".join(hexlified)

    def _encode(self, obj, context, path):
        field_1 = struct.unpack(">L", binascii.unhexlify(obj[:4]))
        field_2 = struct.unpack(">H", binascii.unhexlify(obj[4:6]))
        field_3 = struct.unpack(">H", binascii.unhexlify(obj[6:8]))
        field_4 = struct.unpack("<Q", binascii.unhexlify(obj[8:]))
        return STRUCT_GUID.build(dict(field_1=field_1, field_2=field_2, field_3=field_3, field_4=field_4))


ZONE = Enum(Byte, none=0, character=1, spell=2, treasure=3, hero=4, hand=5, shop=6)  # TODO: Incomplete

SUBTYPE = Enum(Int16ul, prince=0, princess=1, animal=2, mage=4, fairy=6, dwarf=7, treant=8, egg=9, good=0xA, evil=0xB,
               brawl_spell=0xF,
               damage_spell=0x10, random_spell=0x11, beneficial_spell=0x12)  # TODO: Incomplete

KEYWORD = Enum(Int16ul, ranged=3, quest=5, support=6, slay=7)  # TODO: Incomplete


class ListUnitAdapter(Adapter):
    def _decode(self, obj, context, path):
        if obj == b"\x01":
            return None
        else:
            return obj[1]

    def _encode(self, obj, context, path):
        if obj is None:
            return b"\x01"
        else:
            return Sequence(Const(b"\x00"), obj)


STRUCT_OPTIONAL_LIST_GUID = Select(Const(b"\x01"),
                                   Sequence(Const(b"\x00"), PrefixedArray(Int32ul, GuidAdapter(STRUCT_GUID))))

STRUCT_UNIT = Struct(
    "card_id" / GuidAdapter(STRUCT_GUID),
    "template_id" / Int32ul,
    Padding(1),
    "is_locked" / Flag,
    "is_targeted" / Flag,  # Some of these still aren't tested
    "is_golden" / Flag,
    "is_movable" / Flag,
    "makes_pair" / Flag,
    "makes_triple" / Flag,
    "zone" / ZONE,
    "slot" / Int32sl,
    "cost" / Int32ul,
    "attack" / Int32ul,
    "health" / Int32ul,
    "counter" / Int32sl,
    "damage" / Int32sl,
    Padding(1),
    "subtypes" / PrefixedArray(Int32ul, SUBTYPE),
    Padding(1),
    "keywords" / PrefixedArray(Int32ul, KEYWORD),
    "valid_targets" / ListUnitAdapter(STRUCT_OPTIONAL_LIST_GUID),
    "card_id_again" / GuidAdapter(STRUCT_GUID),
    "art_id_length" / Int32ul,
    "art_id" / PaddedString(this.art_id_length * 2, "utf_16_le"),
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "frame_override_length" / Int32ul,
    "frame_override" / PaddedString(this.frame_override_length * 2, "utf_16_le"),
)

STRUCT_LIST_UNIT = Select(Const(b"\x01"), Sequence(Const(b"\x00"), STRUCT_UNIT))

STRUCT_ACTION_ADD_PLAYER = Struct(
    "action_id" / Const(b"\x02\x00"),
    "timestamp" / Int64ul,
    "health" / Int32ul,
    "gold" / Int32ul,
    "experience" / Int32ul,
    "next_level_xp" / Int32ul,
    "level" / Int32ul,
    "place" / Int32ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "player_name_length" / Int32ul,
    "player_name" / PaddedString(this.player_name_length * 2, "utf_16_le"),
    Padding(1),
    "card_id" / GuidAdapter(STRUCT_GUID),
    "template_id" / Int32ul
)

STRUCT_ACTION_ATTACK = Struct(
    "action_id" / Const(b"\x1C\x00"),
    "timestamp" / Int64ul,
    "attacker" / GuidAdapter(STRUCT_GUID),
    "defender" / GuidAdapter(STRUCT_GUID),
    Padding(1)
)

STRUCT_ACTION_BRAWL_COMPLETE = Struct(
    "action_id" / Const(b"\x21\x00"),
    "timestamp" / Int64ul,
    "unknown_1" / Int8ub,  # Always 0? Padding byte?
    "round" / Int32ul,  # This is a guess
    "id_1_length" / Int32ul,
    "player_id_1" / PaddedString(this.id_1_length * 2, "utf_16_le"),
    "id_2_length" / Int32ul,
    "player_id_2" / PaddedString(this.id_2_length * 2, "utf_16_le"),
)

STRUCT_ACTION_CAST_SPELL = Struct(
    "action_id" / Const(b"\x0E\x00"),
    "timestamp" / Int64ul,
    "card_id" / GuidAdapter(STRUCT_GUID),
    "target" / GuidAdapter(STRUCT_GUID)
)

STRUCT_ACTION_CONNECTION_INFO = Struct(
    "action_id" / Const(b"\x01\x00"),
    "timestamp" / Int64ul,
    "session_length" / Int32ul,
    "session_id" / PaddedString(this.session_length * 2, "utf_16_le"),
    "build_length" / Int32ul,
    "build_id" / PaddedString(this.build_length * 2, "utf_16_le"),
    "server_length" / Int32ul,
    "server_ip" / PaddedString(this.server_length * 2, "utf_16_le"),
)

STRUCT_ACTION_CREATE_CARD = Struct(
    "action_id" / Const(b"\x0B\x00"),
    "timestamp" / Int64ul,
    "card" / STRUCT_UNIT,
)

STRUCT_ACTION_DEAL_DAMAGE = Struct(
    "action_id" / Const(b"\x1D\x00"),
    "timestamp" / Int64ul,
    "target" / GuidAdapter(STRUCT_GUID),
    "source" / GuidAdapter(STRUCT_GUID),
    "damage" / Int32ul
)

STRUCT_ACTION_DEATH = Struct(
    "action_id" / Const(b"\x1B\x00"),
    "timestamp" / Int64ul,
    "target" / GuidAdapter(STRUCT_GUID)
)

STRUCT_ACTION_EMOTE = Struct(
    "action_id" / Const(b"\x19\x00"),
    "timestamp" / Int64ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "emote_name_length" / Int32ul,
    "emote_name" / PaddedString(this.emote_name_length * 2, "utf_16_le")
)

STRUCT_ACTION_ENTER_BRAWL_PHASE = Struct(
    "action_id" / Const(b"\x1A\x00"),
    "timestamp" / Int64ul,
    Padding(1),
    "player_1_health" / Int32ul,
    Padding(20),
    "player_1_id_length" / Int32ul,
    "player_1_id" / PaddedString(this.player_1_id_length * 2, "utf_16_le"),
    "player_1_name_length" / Int32ul,
    "player_1_name" / PaddedString(this.player_1_name_length * 2, "utf_16_le"),
    Padding(1),
    "player_1_card_id" / GuidAdapter(STRUCT_GUID),
    "player_1_card_template_id" / Int32ul,
    Padding(1),
    "player_2_health" / Int32ul,
    Padding(20),
    "player_2_id_length" / Int32ul,
    "player_2_id" / PaddedString(this.player_2_id_length * 2, "utf_16_le"),
    "player_2_name_length" / Int32ul,
    "player_2_name" / PaddedString(this.player_2_name_length * 2, "utf_16_le"),
    Padding(1),
    "player_2_card_id" / GuidAdapter(STRUCT_GUID),
    "player_2_card_template_id" / Int32ul,
    "player_1_id_length_again" / Int32ul,
    "player_1_id_again" / PaddedString(this.player_1_id_length_again * 2, "utf_16_le"),
    "player_2_id_length_again" / Int32ul,
    "player_2_id_again" / PaddedString(this.player_2_id_length_again * 2, "utf_16_le"),
)

STRUCT_ACTION_ENTER_INTRO_PHASE = Struct(
    "action_id" / Const(b"\x11\x00"),
    "timestamp" / Int64ul
)

STRUCT_ACTION_ENTER_RESULTS_PHASE = Struct(
    "action_id" / Const(b"\x13\x00"),
    "timestamp" / Int64ul,
    "health" / Int32ul,
    "gold" / Int32ul,
    "experience" / Int32ul,
    "next_level_xp" / Int32ul,
    "level" / Int32ul,
    "place" / Int32ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "player_name_length" / Int32ul,
    "player_name" / PaddedString(this.player_name_length * 2, "utf_16_le"),
    Padding(1),
    "player_hero_id" / GuidAdapter(STRUCT_GUID),
    "player_card_template_id" / Int32ul,
    "placement" / Int32ul,
    "dust_reward" / Int32ul,
    "rank_reward" / Int32sl,
    "crown_reward" / Int32ul,
    "first_win_dust_reward" / Int32ul,
    "unknown" / Int32ul,
    "characters" / PrefixedArray(Int32ul, ListUnitAdapter(STRUCT_LIST_UNIT)),
    "treasures" / PrefixedArray(Int32ul, ListUnitAdapter(STRUCT_LIST_UNIT)),
)

STRUCT_ACTION_ENTER_SHOP_PHASE = Struct(
    "action_id" / Const(b"\x12\x00"),
    "timestamp" / Int64ul,
    "health" / Int32ul,
    Padding(20),
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "player_name_length" / Int32ul,
    "player_name" / PaddedString(this.player_name_length * 2, "utf_16_le"),
    Padding(1),
    "player_card_id" / GuidAdapter(STRUCT_GUID),
    "player_card_template_id" / Int32ul,
    "opponent_id_length" / Int32ul,
    "opponent_id" / PaddedString(this.opponent_id_length * 2, "utf_16_le"),
    "round" / Int32ul,
    "gold" / Int32ul
)

STRUCT_ACTION_MODIFY_GOLD = Struct(
    "action_id" / Const(b"\x05\x00"),
    "timestamp" / Int64ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "amount" / Int32sl,
)

STRUCT_ACTION_MODIFY_LEVEL = Struct(
    "action_id" / Const(b"\x08\x00"),
    "timestamp" / Int64ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "amount" / Int32sl
)

STRUCT_ACTION_MODIFY_NEXT_LEVEL_XP = Struct(
    "action_id" / Const(b"\x07\x00"),
    "timestamp" / Int64ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "new_value" / Int32sl
)

STRUCT_ACTION_MODIFY_XP = Struct(
    "action_id" / Const(b"\x06\x00"),
    "timestamp" / Int64ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "amount" / Int32sl
)

STRUCT_ACTION_MOVE_CARD = Struct(
    "action_id" / Const(b"\x0D\x00"),
    "timestamp" / Int64ul,
    "card_id" / GuidAdapter(STRUCT_GUID),
    "target_zone" / ZONE,
    "target_index" / Int32ul
)

STRUCT_ACTION_PLAY_FX = Struct(
    "action_id" / Const(b"\x17\x00"),
    "timestamp" / Int64ul,
    "source" / GuidAdapter(STRUCT_GUID),
    "content_id_length" / Int32ul,
    "content_id" / PaddedString(this.content_id_length * 2, "utf_16_le"),
    Padding(1),
    "targets" / PrefixedArray(Int32ul, GuidAdapter(STRUCT_GUID))  # TODO: Check longer array?
)

STRUCT_ACTION_PRESENT_DISCOVER = Struct(
    "action_id" / Const(b"\x03\x00"),
    "timestamp" / Int64ul,
    "choice_text_length" / Int32ul,
    "choice_text" / PaddedString(this.choice_text_length * 2, "utf_16_le"),
    "level" / Int32ul,  # TODO: This is a very speculative guess
    "treasures" / PrefixedArray(Int32ul, ListUnitAdapter(STRUCT_LIST_UNIT)),
)

STRUCT_PRICE = Struct(
    "action_id" / Padding(1),
    "currency_name_length" / Int32ul,
    "currency_name" / PaddedString(this.currency_name_length * 2, "utf_16_le"),
    "price" / Int32ul
)

STRUCT_HERO = Struct(
    "unknown" / Int8ub,
    "card" / STRUCT_UNIT,
    Padding(1),
    "prices" / PrefixedArray(Int32ul, STRUCT_PRICE),
)

STRUCT_ACTION_PRESENT_HERO_DISCOVER = Struct(
    "action_id" / Const(b"\x04\x00"),
    "timestamp" / Int64ul,
    "choice_text_length" / Int32ul,
    "choice_text" / PaddedString(this.choice_text_length * 2, "utf_16_le"),
    "heroes" / PrefixedArray(Int32ul, STRUCT_HERO),
)

STRUCT_ACTION_REMOVE_CARD = Struct(
    "action_id" / Const(b"\x0C\x00"),
    "timestamp" / Int64ul,
    "card_id" / GuidAdapter(STRUCT_GUID)
)

STRUCT_ACTION_ROLL = Struct(
    "action_id" / Const(b"\x0A\x00"),
    "timestamp" / Int64ul
)

STRUCT_ACTION_UPDATE_CARD = Struct(
    "action_id" / Const(b"\x15\x00"),
    "timestamp" / Int64ul,
    "card" / STRUCT_UNIT,
)

STRUCT_EMOTE = Struct(
    "emote_name_length" / Int32ul,
    "emote_name" / PaddedString(this.emote_name_length * 2, "utf_16_le")
)

STRUCT_ACTION_UPDATE_EMOTES = Struct(
    "action_id" / Const(b"\x09\x00"),
    "timestamp" / Int64ul,
    "player_id_length" / Int32ul,
    "player_id" / PaddedString(this.player_id_length * 2, "utf_16_le"),
    "emotes" / PrefixedArray(Int32ul, STRUCT_EMOTE)
)

STRUCT_ACTION_UPDATE_TURN_TIMER = Struct(
    "action_id" / Const(b"\x18\x00"),
    "timestamp" / Int64ul,
    "seconds_remaining" / Int32ul,
    "is_enabled" / Flag,
    "timer" / Float32l,

)

STRUCT_ACTION = Select(
    STRUCT_ACTION_ATTACK,
    STRUCT_ACTION_ADD_PLAYER,
    STRUCT_ACTION_BRAWL_COMPLETE,
    STRUCT_ACTION_CAST_SPELL,
    STRUCT_ACTION_CONNECTION_INFO,
    STRUCT_ACTION_CREATE_CARD,
    STRUCT_ACTION_DEAL_DAMAGE,
    STRUCT_ACTION_DEATH,
    STRUCT_ACTION_EMOTE,
    STRUCT_ACTION_ENTER_BRAWL_PHASE,
    STRUCT_ACTION_ENTER_INTRO_PHASE,
    STRUCT_ACTION_ENTER_RESULTS_PHASE,
    STRUCT_ACTION_ENTER_SHOP_PHASE,
    STRUCT_ACTION_MODIFY_GOLD,
    STRUCT_ACTION_MODIFY_LEVEL,
    STRUCT_ACTION_MODIFY_NEXT_LEVEL_XP,
    STRUCT_ACTION_MODIFY_XP,
    STRUCT_ACTION_MOVE_CARD,
    STRUCT_ACTION_PLAY_FX,
    STRUCT_ACTION_PRESENT_DISCOVER,
    STRUCT_ACTION_PRESENT_HERO_DISCOVER,
    STRUCT_ACTION_REMOVE_CARD,
    STRUCT_ACTION_ROLL,
    STRUCT_ACTION_UPDATE_CARD,
    STRUCT_ACTION_UPDATE_EMOTES,
    STRUCT_ACTION_UPDATE_TURN_TIMER
)

id_to_action_name = {b'\x01\x00': 'ActionConnectionInfo',
                     b'\x02\x00': 'ActionAddPlayer',
                     b'\x03\x00': 'ActionPresentDiscover',
                     b'\x04\x00': 'ActionPresentHeroDiscover',
                     b'\x05\x00': 'ActionModifyGold',
                     b'\x06\x00': 'ActionModifyXP',
                     b'\x07\x00': 'ActionModifyNextLevelXP',
                     b'\x08\x00': 'ActionModifyLevel',
                     b'\t\x00': 'ActionUpdateEmotes',
                     b'\n\x00': 'ActionRoll',
                     b'\x0b\x00': 'ActionCreateCard',
                     b'\x0c\x00': 'ActionRemoveCard',
                     b'\r\x00': 'ActionMoveCard',
                     b'\x0e\x00': 'ActionCastSpell',
                     b'\x11\x00': 'ActionEnterIntroPhase',
                     b'\x12\x00': 'ActionEnterShopPhase',
                     b'\x13\x00': 'ActionEnterResultsPhase',
                     b'\x15\x00': 'ActionUpdateCard',
                     b'\x17\x00': 'ActionPlayFX',
                     b'\x18\x00': 'ActionUpdateTurnTimer',
                     b'\x19\x00': 'ActionEmote',
                     b'\x1a\x00': 'ActionEnterBrawlPhase',
                     b'\x1b\x00': 'ActionDeath',
                     b'\x1c\x00': 'ActionAttack',
                     b'\x1d\x00': 'ActionDealDamage',
                     b'!\x00': 'ActionBrawlComplete'}

