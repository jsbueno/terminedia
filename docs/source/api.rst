

Terminedia
===========
.. automodule:: terminedia
   :members:
.. autofunction:: print

This is the most basic and straightforward way to make use of terminedia. It implements
all features from Python built-in print, but will also accept a variety of parameters
to change the text attributes.

Notably, aside from the usual text color, background and terminal effects,
that can be achieved by ANSI codes, one can also use especial `terminedia.Effects` values
that will transform the characters prior to printing, using a variety of special
Unicode character blocks::

    import terminedia as TM

    TM.print("Hello World!", effects=TM.Effects.encircled)

Will print::

    Ⓗⓔⓛⓛⓞ Ⓦⓞⓡⓛⓓ!


Blockchars
------------
.. automodule:: terminedia/subpixels
   :special-members: __init__,__enter__,__exit__,__contains__
