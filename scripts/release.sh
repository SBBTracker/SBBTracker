#!/usr/bin/env bash

. venv/Scripts/activate
bumpversion $1 scr/version.py scripts/sbbt.iss
pyinstaller SBBTracker.spec
"C:/Program Files (x86)/Inno Setup 6/ISCC.exe" scripts/sbbt.iss