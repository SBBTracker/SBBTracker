#!/usr/bin/env bash

./scripts/test.sh
if [[ $? != 0 ]]; then
  exit $?
fi

. venv/Scripts/activate
bumpversion $1
rm -rf ./dist
cd sbbtracker/SBBBattleSim
pip install .
cd ../../
pyinstaller SBBTracker.spec
"C:/Program Files (x86)/Inno Setup 6/ISCC.exe" scripts/sbbt.iss
deactivate