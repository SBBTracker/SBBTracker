#!/bin/bash

version=$(grep "current_version" .bumpversion.cfg | sed s,"current_version = ",,)
rm -rf ./dist
. venv/bin/activate
cd src/SBBBattleSim
pip install .
cd ../../
pyinstaller SBBTracker.spec
cp -r dist/SBBTracker/. release/linux/bin
cp -r assets release/linux/
cp -r cards release/linux/
cd release/
tar -zcvf "SBBTracker-v${version}.tar.gz" linux/ --transform s/linux/SBBTracker-v${version}/
cd ..
deactivate