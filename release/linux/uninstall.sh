#!/bin/bash

set -e

if [ "$PREFIX" = "" ]; then
	PREFIX=/usr/local
fi

rm -rf "$PREFIX"/share/sbbtracker
rm -rf "$PREFIX"/bin/sbbtracker
rm -rf "$PREFIX"/share/pixmaps/sbbtracker.png
rm -rf "$PREFIX"/share/applications/sbbtracker.desktop

echo "Uninstall complete."
