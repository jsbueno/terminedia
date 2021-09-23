from setuptools import setup, find_packages

setup(
    name="terminedia",
    packages=find_packages(),
    version="0.4.2",
    license="LGPLv3+",
    author="João S. O. Bueno",
    author_email="gwidion@gmail.com",
    description="Utilities for drawing and interactiveness at the terminal",
    keywords="terminal cmd posix xterm ANSI color",
    url="https://github.com/jsbueno/terminedia",
    project_urls={
        "Documentation": "https://terminedia.readthedocs.io/en/stable/",
        "Source Code": "https://github.com/jsbueno/terminedia",
    },
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    # use_scm_version=True,
    setup_requires=["setuptools_scm"],
    include_package_data=True,
    zip_safe=True,
    test_requires=[],
    install_requires=["click", 'colorama;platform_system=="Windows"'],
    extras_require={
        "doc": ["Sphinx==2.0.0"],
        "images": ["pillow>=6.0.0"],
        "tests": ["pytest"],
    },
    entry_points="""
        [console_scripts]
        terminedia-bezier=terminedia.examples.bezier:main
        terminedia-context=terminedia.examples.context:main
        terminedia-ellipses=terminedia.examples.ellipses:main
        terminedia-image=terminedia.examples.image:main
        terminedia-lines=terminedia.examples.lines:main
        terminedia-plot=terminedia.examples.plot:main
        terminedia-shapes=terminedia.examples.shapes:main
        terminedia-snake=terminedia.examples.snake:main
        terminedia-effects=terminedia.examples.effects:main
        terminedia-text=terminedia.examples.text:main
    """,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: PyPy",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Topic :: Artistic Software",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Terminals",
        "Topic :: Terminals :: Terminal Emulators/X Terminals",
    ],
)
