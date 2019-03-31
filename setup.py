# coding: utf-8

from setuptools import setup

setup(
    name = 'terminedia',
    py_modules = ["terminedia"],
    version = "0.2.0",
    license = "LGPLv3+",
    author = "João S. O. Bueno",
    author_email = "gwidion@gmail.com",
    description = "Utilities for drawing and interactiveness at the terminal",
    keywords = "terminal cmd posix xterm ANSI color",
    url = "https://github.com/jsbueno/terminedia",
    long_description = open("README.md").read(),
    test_requires = [],
    extras_require = {
        "doc": ["Sphinx==2.0.0"],

    },
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Topic :: Artistic Software",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Terminals",
        "Topic :: Terminals :: Terminal Emulators/X Terminals",
    ]
)
