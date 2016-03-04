#! /usr/bin/env python

from __future__ import print_function
import os
import sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# import shlex
# import subprocess as sub
# from glob import glob

try:
    import PyQt4
except ImportError:
    print("missing dependency: before installing muonic you have to " +
          "install python-qt4 via your distributions package manager first")
    sys.exit(1)

import muonic


def read_file(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()

# build the documentation
# man_make  = "make man -C docs"
# html_make = "make html -C docs"

# man_success = sub.Popen(shlex.split(man_make),
# stdout=sub.PIPE).communicate()
# html_success = sub.Popen(shlex.split(html_make),
# stdout=sub.PIPE).communicate()

data_path = muonic.DATA_PATH

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
      install_requires=["future", "numpy", "scipy", "pyserial", "matplotlib"],
      platforms=["Ubuntu 12.04"],
      scripts=["bin/muonic", "bin/which_tty_daq"],
      packages=["muonic", "muonic.analysis", "muonic.gui", "muonic.daq",
                "muonic.util"],
      package_data={"muonic": ["daq/simdaq.txt", "gui/daq_commands_help.txt"],
                    "": ["*.txt", "*.rst", "*.md"]},
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

# setting correct permissions of created muonic_data dir
#
# userid = os.stat(os.getenv("HOME"))[4]
# gid = os.stat(os.getenv("HOME"))[5]
#
# if muonic is installed with sudo, the ownership of the files
# has to be changed to the current user.
# if os.geteuid() == 0:
#    cline = "chown -R " + str(gid) + ":" + str(userid) + " " + datapath
#    print cline
#
# chown_success = sub.Popen(shlex.split(cline), stdout=sub.PIPE).communicate()
#
# print man_success[0]
# print html_success[0]
# if chown_success[1] is None:
#    print "Successfully changed owner of %s to %s" %(datapath, str(userid))
#    print "---------------------------"
#
# if man_success[1] is None:
#    print "Built manpages succesfully"
#    print "---------------------------"
# if html_success[1] is None:
#    print "Buitl html docs succesfully"
#    print "---------------------------"
#
# print "MUONIC succesfully installed!"
