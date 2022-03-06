def round_to_xp(round_number: int):
    lvl = min(6, (round_number - 1) // 3 + 2)
    xp = (round_number - 1) % 3 if lvl != 6 else round_number - 13
    return "0.0" if round_number == 0 else f"{lvl}.{xp}"
