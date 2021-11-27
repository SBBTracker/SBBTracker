#!/bin/bash

set -e

if ! test -f install.sh; then
  echo "Please run from the folder install.sh is in."
  exit 1
fi

if [ "$PREFIX" = "" ]; then
	PREFIX=/usr/local
fi

rm -rf "$PREFIX"/share/sbbtracker "$PREFIX"/bin/sbbtracker
mkdir -p "$PREFIX"/share/sbbtracker
cp -av * "$PREFIX"/share/sbbtracker/
mkdir -p "$PREFIX"/bin
ln -sf "$PREFIX"/share/sbbtracker/bin/SBBTracker "$PREFIX"/bin/sbbtracker
(test -f "$PREFIX"/share/applications && rm "$PREFIX"/share/applications)||true
mkdir -p "$PREFIX"/share/pixmaps
mkdir -p "$PREFIX"/share/applications
mkdir -p "$PREFIX"/share/man/man1
cd "$PREFIX"/share/sbbtracker && (\
cp assets/icon.png "$PREFIX"/share/pixmaps/sbbtracker.png;\
mv sbbtracker.desktop "$PREFIX"/share/applications/)

echo "Install complete. Type 'sbbtracker' to run."
