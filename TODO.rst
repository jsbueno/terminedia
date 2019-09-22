version 0.3
============

Bezier curves primitive (v)
2D Vector class (v)
PNM Image File loading and Displaying (v)
Shape Class (v)
Image File Displaying Support(v)
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
    Fallback terminal to 1-byte color setting for up to 216 colors + 24 grayscale

alpha channel support for images
Single-write optimization
support to z-index, and background keeping on blitting ("sprite" api)
REPL Environment wit bottom lines for python console and upper screen for image
MS-Windows support (colorama/mscrvt/color reducing)
"business" framed-window api
Postscriptish/Turtleish drawing api
Basic image transform API: resize, rotate, flip.
Table drawing chars drawing API
Super-high resolution (Unicode vintage charset and "sextant" blocks)
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
replicate text-char effects for big-chars


frontend:
Graph plotting CLI
    make terminedia avalilable as a matplotlib backend

gradient fun: functions to apply color gradients
    easily on existing content (shapes)

alpha emulation using background and color manipulation

gaming framework in general:
    sprites
    physics engine (minimal, 2D)
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
        use "imp.resource" to read default font data (allows terminedia to run from zipped egg) (V)
    create "render text" call returning a shape (V)
    create "render text and blit at position on screen" call on drawing api (V)
    read font on demand (WIP - only the first 256 chars are loaded)
    Improve font selection and loading
    Bundle 8x16 UNSCII font to packages
    Add arbitrary font handling by using PIL to cache rendered chars.
    write example script using large-text rendering (V)


Imaging capabilities:
    make "Alpha" value work for value-shapes.
    make "intensity" rendering for values (B&W shapes)

    create full fledged shape with char, fg, bg, effects (WIP):
        implement FullShape class (v)
        make text effects work on terminal (V)
        Associate a base FullShape class with a Screen (V)
        Add example with terminal text effects(V)
        Add example using FullShape
        enable rendering of pixels with char, fg, bg, effects on screen (V)
        enable rendering of arbitrary pixels on arbitrary shape types (WIP)
        update blit and other actions on drawing api to use all pixel properties. (WIP)
        implement handling of "TRANSPARENT" as FG, BG and Effects keeping attribute.
    create a "blit fast path" for value/palette shapes to target
        (avoid overhead of pixel creation)

General Refactoring:
    refactor context initialization (V)
    Add a proper rectangle class
    create a proper color class
    write a refresh method to redraw a Screen rectangle given internal data
    improve "blit" to allow optional source and destination ROI
    (them proceed to write the different backends.)
    Convert directions to specialized V2s, with a nice repr, instead of Enums (they have to be interchangeable with plain V2)

Improvements and bugs:
    CRITICAL: effects refactoring led rendering to be B&W (V)
    Text effects are not cached in the terminal journaling-commands (V)
    Fix tm.text.render into palettedshape: result is mixing spaces and color-constants in data
    make double-width unicode characters take 2 character cells.
    plot example script prints completly bogus values on the y scale.
    Fix text rendering into FullShape
    Fix blitting from FullShape
    fix-paletted-shape-blitting-bug (WIP)
    fix-value-shape-blitting-bug
    fix-highres-shape-bliting color leak
    refactor bezier-curve and ellipse(empty) adaptive code to use same codebase
    configure properly and make consistent use of logger
    fix breaking on terminedia-context (context initialization) (V)
    fix regression on terminedia-context
