"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
import pathlib
from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name="openinverter-can-tool",  # Required
    version="0.0.3",  # Required
    description="Tool to configure and operate openinverter systems over CAN",
    long_description=long_description,  # Optional
    long_description_content_type="text/markdown",  # Optional
    url="https://github.com/davefiddes/openinverter-can-tool",  # Optional
    author="David J. Fiddes",  # Optional
    author_email="D.J@fiddes.net",  # Optional
    # Classifiers help users find your project by categorizing it.
    #
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
    ],

    keywords="openinverter, canopen",  # Optional

    package_dir={"": "src"},  # Optional
    packages=find_packages(where="src"),  # Required
    python_requires=">=3.7, <4",

    install_requires=["click", "canopen"],  # Optional
    extras_require={  # Optional
        "dev": ["check-manifest", "flake8"],
        "test": ["coverage", "pytest"],
    },

    # No data files are expected within the package
    package_data={},

    # Pull in all our example parameter databases
    data_files=[("parameter-databases",
                 ["parameter-databases/c2000-sine.5.14.R.C2000-foc.json",
                  "parameter-databases/stm32-sine.5.24.R-foc.json",
                  "parameter-databases/stm32-sine.5.24.R-sine.json"])],

    # The main command-line tool
    entry_points={
        "console_scripts": [
            "oic=openinverter_can_tool:cli.cli"
        ],
    },
    # List additional URLs that are relevant to your project as a dict.
    #
    # This field corresponds to the "Project-URL" metadata fields:
    # https://packaging.python.org/specifications/core-metadata/#project-url-multiple-use
    #
    # Examples listed include a pattern for specifying where the package tracks
    # issues, where the source is hosted, where to say thanks to the package
    # maintainers, and where to support the project financially. The key is
    # what's used to render the link text on PyPI.
    project_urls={  # Optional
        "Bug Reports":
            "https://github.com/davefiddes/openinverter-can-tool/issues",
        "Source":
            "https://github.com/davefiddes/openinverter-can-tool",
    },
)
