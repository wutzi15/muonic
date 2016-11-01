#!/usr/bin/env python
from __future__ import print_function
import os
import sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:
    import PyQt4
except ImportError:
    print("missing dependency: before installing muonic you have to " +
          "install python-qt4 via your distributions' package manager")
    sys.exit(1)

import muonic


def read_file(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()

setup(name=muonic.__name__,
      version=muonic.__version__,
      author=muonic.__author__,
      author_email=muonic.__author_email__,
      description=muonic.__description__,
      long_description=read_file("README.md"),
      license=muonic.__license__,
      keywords=["QNET", "QuarkNET", "Fermilab", "DESY", "DAQ"],
      url=muonic.__source_location__,
      download_url=muonic.__download_url__,
      install_requires=["future", "matplotlib", "numpy", "pyserial", "scipy"],
      platforms=["Ubuntu 12.04"],
      scripts=["bin/muonic", "bin/which_tty_daq"],
      packages=["muonic", "muonic.analysis", "muonic.daq",
                "muonic.gui", "muonic.util"],
      package_data={"muonic": ["daq/simdaq.txt", "gui/daq_commands_help.txt",
                              "gui/muonic.xpm"]},
      classifiers=[
          "License :: OSI Approved :: GNU General Public License v3 or " +
          "later (GPLv3+)",
          "Development Status :: 4 - Beta",
          "Intended Audience :: Science/Research",
          "Intended Audience :: Education",
          "Intended Audience :: Developers",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Topic :: Scientific/Engineering :: Physics"
      ])
