#!/usr/bin/python
from urllib.request import urlopen
import json, string
from logging import getLogger

logger = getLogger(__file__)

"""
Downloads the slugged nicknames used by Github markup for emojis, and
generates data file used by terminedia internally
"""

def fetchall():
    urls = json.loads(urlopen("https://api.github.com/emojis").read().decode())

    codes = {}
    for nick, url in urls.items():
        code = url.split("/")[-1].split(".")[0]
        if any(d not in string.hexdigits for d in code):
            logger.warning("Not valid hex - ignored: %s, %s", nick, url)
            continue
        charseq = ""
        for code_part in code.split("_"):
            charseq += chr(int(code_part, 16))
        codes[nick] = charseq

    return codes

if __name__ == "__main__":
    from pprint import pprint
    pprint(fetchall())


