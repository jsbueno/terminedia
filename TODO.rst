version 0.3
============

Bezier curves primitive (v)
2D Vector class (v)
PNM Image File loading and Displaying (v)
Shape Class (v)
    - with support to z-index, and background keeping
Image File Displaying Support(v)
    - with alpha support
Preliminary CLI (v)
move examples to CLI-based standalone scripts available to pip-installs (v)
refactor into full package (v)
Big Font rendering - using multi-block for large characters composed of multiple pixels. (WIP)
Bold, blink and underline text support (WIP)
raw-data backend (terminal indepent)
Block-smoothing with half triangle block chars


Future
========

multiple backends: (check pygments):
    HTML backend
    Image 'screenshot' backend
    image backend (pixels are simple color-only boring, image pixels)
    postscript backend
    .rtf backend

Single-write optimization
REPL Environment wit bottom lines for python console and upper screen for image
MS-Windows support (colorama/mscrvt/color reducing)
"business" framed-window api
Postscriptish/Turtleish drawing api
Table drawing chars drawing API
Super-high resolition (Unicode vintage charset and "sextant" blocks)
Mouse event support
Audio support (pyAudio?)
Image (shape) transform - (rotate, scale).
paint modes to use different characters to denote intensity (back do ascii art):
    unicode circles
    unicode squares
    Classic ASCII # * . etc
    Block-smoothing with half triangle block chars
    (use a context "paint mode" to have this supported on all paint operations?)

"gradients": ways to make easy to create gradually changing colors.
             possibly a "painting context" similar to Cairo's, instead
             of a plain value for foreground color. Then color
             for each pixel could be sourced from a shape, image,
             gradient, whatever.
             But whatever is done, have ways for it being simpler to
             use than cairo's contexts.'


frontend:
Graph plotting CLI
    make terminedia avalilable as a matplotlib backend

gradient fun: functions to apply color gradients
    easily on existing content (shapes)

alpha emulation using brackground and color manipulation

gaming framework in general:
    sprites
    physics engine
    animation support
    main loop

space invaders

##############
step by step tasks

for sane text rendering:

    enable new blank shape with given size (V)
    sanitizing load from data for shapes(V)
    enable drawing context and api for shapes(V)
    enable shape drawing (V)
    enable shape blit (V)
    write shape-concatenation method (V)
        use "imp.resource" to read default font data (V)
    create "render text" call returning a shape (V)
    create "render text and blit at position on screen" call on drawing api
    fix-paletted-shape-blitting-bug (WIP)
    read font on demand (WIP - only the first 256 chars are loaded)
    Improve font selection and loading
    Bundle 8x16 UNSCII font to packages
    Add arbitrary font handling by using PIL to cache rendered chars.


Imaging capabilities:
    make "Alpha" value work for value-shapes.
    make "intensity" rendering for values

    create full fledged shape with char, fg, bg, effects (WIP)
    enable rendering of pixels with char, fg, bg, effects
    update blit and other actions on drawing api to use all pixel properties.
    enable rendering of text effects on screen

General Refactoring:
    Use base Shape class for Screen.
    Add a proper rectangle class
    improve "blit" to allow optional source and destination ROI
