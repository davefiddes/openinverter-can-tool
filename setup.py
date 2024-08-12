"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
import pathlib
import re
from glob import glob
from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

# Strip the build status as this only makes sense on github
long_description = re.sub(r'\[!\[Build status.*\)\n\n', '', long_description)

setup(
    name="openinverter-can-tool",
    version="0.2.0",
    description="Tool to configure and operate openinverter systems over CAN",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/davefiddes/openinverter-can-tool",
    author="David J. Fiddes",
    author_email="D.J@fiddes.net",

    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
    ],

    keywords="openinverter, canopen",

    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8, <4",

    install_requires=[
        "click",
        "canopen",
        "appdirs",
        "python-can",
        "cantools"],

    extras_require={
        "dev": [
            "check-manifest",
            "flake8",
            "pre-commit"
        ],
        "test": [
            "coverage",
            "pytest",
            "approvaltests",
            "pytest-approvaltests"
        ],
    },

    # No data files are expected within the package
    package_data={},

    # Pull in all our example parameter databases and documentation
    data_files=[("parameter-databases",
                 glob("parameter-databases/*.json")),
                ("docs",
                 glob("docs/*.md") + glob("docs/*.png"))],

    # The main command-line tool
    entry_points={
        "console_scripts": [
            "oic=openinverter_can_tool.__main__:cli"
        ],
    },

    project_urls={
        "Bug Reports":
            "https://github.com/davefiddes/openinverter-can-tool/issues",
        "Source":
            "https://github.com/davefiddes/openinverter-can-tool",
    },
)
