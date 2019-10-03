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
Big Font rendering - using multi-block for large characters composed of multiple pixels. (V)
Bold, blink and underline text support (V)
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
    pdf backend
    Fallback terminal to 1-byte color setting for up to 216 colors + 24 grayscale

new "resolution modes":
    - half character (1/2 block - square aspect ratio)
    - double-character (2 blocks - square aspect ratio)
    - braille-block (1/8 block)
    - sextant (1/6 block) (depends on unicode 12 with vintage charset), with square aspect ratio:
    - indexed-name-space based resolution, as we have for ".text[size]"
    - 1 block width x 1 block height at arbitrary 1/8 block height position. (use "LOWER ONE EIGHTH BLOCK" and friends)
    - 1 block width x 1 block height at arbitrary 1/8 block width position.

unicode latin-effected characters as character effects:
    (like digits and letters inside squares and circles, combining stroke, underline, slash, and so on)
    (should use the "Effects" space currently marking terminal-wise text effects,
     and be applied only at rendering time - "value_data" structures should retain page-0 range latin text)
     - encircled chars(V)
     - squared chars(V)
     - Reversed squared chars(WIP)
     - Small (combining?) chars
     - Fix internal data and cursor positioning for non-single width characters


convolution-dependant effects, to smooth-out corners, use unicode circles and squares to denote intensity
    (should use transformers, and be applied at painting time)
"page" abstraction expanding the "shape": including text regions, layers and animation effects
easy way to pick unicode emojis and glyphs

alpha channel support for images
Single-write optimization
support to z-index, and background keeping on blitting ("sprite" api)
MS-Windows support (colorama/mscrvt/color reducing)
"business" framed-window api
Postscriptish/Turtleish drawing api
Basic image transform API: resize, rotate, flip.
Table drawing chars drawing API (maybe convert chars with a convolution after block-line art?)
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
    (use a special "effects" attribute and apply a convolution variant with a transformer?)

"gradients": ways to make easy to create gradually changing colors.
             possibly a "painting context" similar to Cairo's, instead
             of a plain value for foreground color. Then color
             for each pixel could be sourced from a shape, image,
             gradient, whatever.
             But whatever is done, have ways for it being simpler to
             use than cairo's contexts.'
             (Hint: already possible on "user side" by using context-transformers)

replicate text-char effects for big-chars

frontend:
Graph plotting CLI
    make terminedia available as a matplotlib backend

alpha emulation using background and color manipulation

gaming framework in general:
    (integrate as a backend to "jsbueno/mapengine"?)
    sprites
    physics engine (minimal, 2D)
    animation support
    main loop

space invaders implementation (hint: it would be already feasible - but it is still a "landmark" of the roadmap)


# virtual terminal server-
    use advanced

Advanced terminal handling features
    REPL Environment wit bottom lines for python console and upper screen for image (see posix_openpt)
    anmating and coloring text output of unware apps, by creating an internal virtual terminal (posix_openpt)
    handle scrolling capabilities and pre-post buffer
    terminal agnostic screen commands (terminfo and infocmp to de-hardcode ANSI sequences)

HTML Backend:
    generate static html files with inline style
    server/mini app to live update a terminal HTML component
    Ability to emulate Unix terminal on HTML comonent (posix_openpt)
    Full-client-side implementation (using brython)


Ongoing (0.3dev)
###############
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
    write example script using large-text rendering (V)
    connect Screen "print" and "print_at" to ".text" namespace.(V)

    Add text formatting and flowing primitives into ".text" namespace
    Add scrolling, rectangular text regions and flowing text
    All-side scrolling and flowing text from one region to the next

    (make text.at work with the @ operator?: `sc.text[4] @ (5,2)("hello!")(?)
    read font "planes" on demand (WIP - only the first 256 chars are loaded)
    Improve font selection and loading (V)
    Bundle 8x16 UNSCII font to packages (whooping 3.5MB) (V)
    Find proper API do render 8x16 pixel fonts into 8x8 char "high-resolution" 1/4 block.
    Add arbitrary font handling by using PIL to cache rendered chars.
    Enable 16 x 8 double and 16 x 16 double width UNSCII fonts.

create full fledged shape with char, fg, bg, effects (WIP):
    implement FullShape class (V):
        class with internal data planes for each attribute (V)
        class bound as internal storage for screen (V)
        bug: issues with internal data and rendering(V)
        Fix text rendering into FullShape(V)
        FEATURE: being able to draw in differing planes (value, FG, BG, effects) independent way(V)
        write a refresh method to redraw a Screen rectangle - allowing double-buffering drawing (V)
    Add example script using FullShape and transformers(terminedia-text)


Imaging capabilities:
    make "Alpha" value work for value-shapes.
    make "intensity" rendering for values (B&W shapes)
        make text effects work on terminal (V)
        Associate a base FullShape class with a Screen (V)
        Add example with terminal text effects(V)
        enable rendering of pixels with char, fg, bg, effects on screen (V)
        enable rendering of arbitrary pixels on arbitrary shape types (V)
        update blit and other actions on drawing api to use all pixel properties. (V) (via context.transfomer)
        implement handling of "TRANSPARENT" as FG, BG and Effects keeping attribute (V)
    create a "blit fast path" for value/palette shapes to target
        (avoid overhead of pixel creation)

General Refactoring:
    refactor context initialization (V)
    Convert directions to specialized V2s, with a nice repr, instead of Enums (they have to be interchangeable with plain V2) (V)
    Add a proper rectangle class (V)
    Refactor APIs to accept Rectangle(V)
    Introduce "Shape view" so that shape-slices work like a rectangular view with no data-copying (V)
    improve "blit" to allow optional source and destination ROI (WIP)
    (them proceed to write the different backends.)
    create a proper color class:
        - Accept 0-255 or 0-1.0 3 [4] sequences for RGB color [Alpha]
        - Accept internal constants and a have a proper way to check for then
                 (defaultFG, defaultBG, Transparent, context)
        - Normalized reading and representation
        - conversion to 1-byte standard 216 color palette for terminals
        - make use of 1byte color on terminal.py


Improvements and bugs:
    CRITICAL: effects refactoring led rendering to be B&W (V)
    Text effects are not cached in the terminal journaling-commands (V)
    Fix tm.text.render into palettedshape: result is mixing spaces and color-constants in data
    make double-width unicode characters take 2 character cells.
    plot example script prints completly bogus values on the y scale.
    Fix blitting from FullShape (V)
    fix-paletted-shape-blitting-bug
    fix-value-shape-blitting-bug
    fix-highres-shape-bliting color leak
    refactor bezier-curve and ellipse(empty) adaptive code to use same codebase
    configure properly and make consistent use of logger
    fix breaking on terminedia-context (context initialization) (V)
    fix regression on terminedia-context (V)
    Improve error messages/or silence/ when attempting to write out of Screen/Shape limits
    FIX DOCUMENTATION GENERATION
    Bug: current "inkey" is buggy as repeated keystrokes are bundled in the same inkey response. (completly bork at higher repeat rates)(V)
    improvement: API for  X-session wide key-repeat tunning with "xset r rate".
            (Maybe, in combination with other features, it is even possible to have keydown/keyup emulation)
            What is the equivalent API for Win and Mac if any?
    Make internal FullShape planes (and maybe other Shapes) specialized containers (they are plain lists): enable direct attribute setting on plane (rename  attributes in the process) (maybe trim further down shape class, and make internal planes for shapes, shapes as well?)
    Improve context transformers to become a friendly, stackable class
    create a few ready-made, parametrized transformers for effects like: plane select, color gradients, mask blit,
    Refactor "context" namespace into full class with descriptors. (V)
    Update "Context" to use context-locals (async aware) instead of thread-locals
    Add a "clear" draw method to empty-up a target.
    Drawing APIs not respecting ShapeView limits (V)
    Optimize extent-limted blitting to skip fast to next shape line (by sending a next-line sentinel to shape-iterator) (V)


