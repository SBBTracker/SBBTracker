#!/usr/bin/python
from pathlib import Path

from PIL import Image
import os, sys

# https://drive.google.com/drive/folders/1bA-tChpvQj39tN_0_72e_vJRdph1M_gI
# before running this script, you need to downlaod the cards folder and place the cards folder in the
# root directory of the repo
path = Path(__file__).parent.joinpath("cards")
dirs = os.listdir(path)


def resize():
    for item in dirs:
        if os.path.isfile(path + item):
            im = Image.open(path + item)
            f, e = os.path.splitext(path + item)
            imResize = im.resize((180, 256), Image.ANTIALIAS)
            imResize.save(f + '.png', 'png', quality=90)


resize()
