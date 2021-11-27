#!/bin/bash

version=$(grep "current_version" .bumpversion.cfg | sed s,"current_version = ",,)
rm -rf ./dist
. venv/bin/activate
pyinstaller SBBTracker.spec
cp -r dist/SBBTracker/. release/linux/bin
cp -r assets release/linux/assets
cp -r cards release/linux/cards
cd release/
tar -zcvf "SBBTracker-v${version}.tar.gz" linux/ --transform s/linux/SBBTracker-v${version}/
cd ..
deactivate