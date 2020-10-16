Related projects
================

Related projects providing resources that enable a better use of Terminedia,
or simply do similar things, or are essential for working with terminedia:

# UNSCII font project:
http://pelulamu.net/unscii/
The UNSCII fonts are a few fonts created thinking in
vintage text-art, extending it to UNICODE.
Actually, terminedia currently _embedds_ the raster version
of all UNSCII fonts, and those are used for drawing large-block
text. Besides that, it is a very useful font, if not essential,
to use terminedia under Windows, as it features the block-characters
that are used as pixels.

# Rbanffy's 3270font
# Install this for best experience with Unicode 13.0 Sextant characters
https://github.com/rbanffy/3270font

# CMDER terminl emulator
https://cmder.net/
Rather complete terminal experience made available under Windows.
AMong other things, allow easy configuring of the fonts to be used
for graphics (see UNSCII above), without which terminedia drawing
simply won´t work.


And now for some similar projects
=======================================

# Plotting using Braille characters (Lua)
https://github.com/asciimoo/lua-drawille

# Converting images to colored UNICODE output (Python)
https://github.com/kelvindecosta/picharsso

# Full color using half-blocks images on terminal (rust)
https://github.com/atanunq/viu

# Extended API iterminal emulator  (C + Python):
https://github.com/kovidgoyal/kitty

# Colored and ANSI effects printing on terminal:

#   - termcolor
https://pypi.org/project/termcolor/

#   - rich
https://pypi.org/project/rich/

#   - colorama
https://pypi.org/project/colorama/
(NB: Colorama is usd by terminedia itself on Windows, as has a "low level" api that makes
the ANSI codes interface seamlessly available on that system)

# python-prompt-toolkit
Mature project for creating terminal GUI with mouse support and widgets -
(including, for examle, a Python VIM clone)
https://github.com/prompt-toolkit/python-prompt-toolkit

Simpler projects dealing with subsets of character/effect mangling
===================================================================

We can use some ideas/data from these projects -
proper credit is given on code inline comments where this happens:

# Python upsidedown  by Christoph Burgmer
Simpler converter/printer to upsidedown pseudo text:
https://github.com/cburgmer/upsidedown by Christoph Burgmer

(Pseudo upside down mapping originally lifted from fileformat.info/)


