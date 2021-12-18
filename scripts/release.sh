#!/usr/bin/env bash

. venv/Scripts/activate
bumpversion $1
rm -rf ./dist
cd src/SBBBattleSim
pip install .
cd ../../
pyinstaller SBBTracker.spec
"C:/Program Files (x86)/Inno Setup 6/ISCC.exe" scripts/sbbt.iss
deactivate