from pygtail import Pygtail
from pathlib import Path
import sys
import os
import re

appdata = Path(os.environ["APPDATA"])
logfile = appdata.parent.joinpath("LocalLow/Good Luck Games/Storybook Brawl/Player.log")

def parseLine(line):
    if "Type:" in line:
        trimmed = line[line.index('Type:'):]
        splitlines = re.split("(\w+):", trimmed)
        it = iter(splitlines[1:])
        paired = list(zip(it, it))
        cleaned = clean(paired)
        return cleaned
    else:
        return []

def clean(entries):
    cleaned = {}
    for i in range(len(entries)):
        key = entries[i][0]
        val = entries[i][1].strip().rstrip(" | ")
        if " | " in val:
            val = str(val).split(" | ")
        cleaned[key] = val
    return cleaned

while True:
    for line in Pygtail(str(logfile)):
        print(parseLine(line))
