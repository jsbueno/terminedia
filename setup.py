# coding: utf-8

from setuptools import setup

setup(
    name = 'terminedia',
    packages = ["terminedia"],
    version = "0.3.dev0",
    license = "LGPLv3+",
    author = "João S. O. Bueno",
    author_email = "gwidion@gmail.com",
    description = "Utilities for drawing and interactiveness at the terminal",
    keywords = "terminal cmd posix xterm ANSI color",
    url = "https://github.com/jsbueno/terminedia",
    project_urls={
        "Documentation": "https://terminedia.readthedocs.io/en/stable/",
        "Source Code": "https://github.com/jsbueno/terminedia",
    },
    long_description = open("README.md").read(),
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    test_requires = [],
    install_requires=[
        "click",
        "colorama >= 1.0;platform_system==\"Windows\"",
    ],
    extras_require = {
        "doc": ["Sphinx==2.0.0"],
        "images": ["pillow>=6.0.0"]
    },
    entry_points = """
        [console_scripts]
        terminedia-shapes=terminedia.examples.shapes:main
    """,
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
