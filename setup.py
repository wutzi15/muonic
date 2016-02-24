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

# build the documentation
# man_make  = "make man -C docs"
# html_make = "make html -C docs"

# man_success  = sub.Popen(shlex.split(man_make),stdout=sub.PIPE).communicate()
# html_success = sub.Popen(shlex.split(html_make),stdout=sub.PIPE).communicate()

data_path = muonic.DATA_PATH

setup(name=muonic.__name__,
      version=muonic.__version__,
      description=muonic.__description__,
      long_description=muonic.__long_description__,
      author=muonic.__author__,
      author_email=muonic.__author_email__,
      url=muonic.__source_location__,
      download_url="pip install muonic",
      install_requires=['numpy', 'scipy', 'pyserial', 'matplotlib'],
      license=muonic.__license__,
      platforms=["Ubuntu 12.04"],
      classifiers=[
          "License :: OSI Approved :: GNU General Public License v3 or " +
          "later (GPLv3+)",
          "Development Status :: 4 - Beta",
          "Intended Audience :: Science/Research",
          "Intended Audience :: Education",
          "Intended Audience :: Developers",
          "Programming Language :: Python :: 2.7",
          "Topic :: Scientific/Engineering :: Physics"
      ],
      keywords=["QNET", "QuarkNET", "Fermilab", "DESY", "DAQ"],
      packages=['muonic', 'muonic.analysis', 'muonic.gui', 'muonic.daq'],
      scripts=['bin/muonic', 'bin/which_tty_daq'],
      package_data={'muonic': ['daq/simdaq.txt'], '': ['*.txt', '*.rst']},
      # package_data={'' : ['docs/*','README'], 'muonic': ['daq/simdaq.txt','daq/which_tty_daq']},
      data_files=[(data_path, [])]
      #,(datapath,["muonic/docs/build/man/muonic.1"]),(os.path.join(datapath,"muonic/docs/html"),glob("muonic/docs/build/html/*html")),(os.path.join(datapath,"muonic/docs/html/_static"),glob("muonic/docs/build/html/_static/*")),(os.path.join(datapath,"muonic/docs/html/_modules"),glob("muonic/docs/build/html/_modules/*html")),(os.path.join(datapath,"muonic/docs/html/_sources"),glob("muonic/docs/build/html/_sources/*html")),(os.path.join(datapath,"muonic/docs/html/_modules/muonic/"), glob("muonic/docs/build/html/_modules/muonic/*html")),(os.path.join(datapath,"muonic/docs/html/_modules/muonic/gui"),glob("muonic/docs/build/html/_modules/muonic/*html")),(os.path.join(datapath,"muonic/docs/html/_modules/muonic/daq"),glob("muonic/docs/build/html/_modules/muonic/daq/*html")),(os.path.join(datapath,"muonic/docs/html/_modules/muonic/analysis"), glob("muonic/docs/build/html/_modules/muonic/analysis/*html"))]
)

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
#    chown_success = sub.Popen(shlex.split(cline),stdout=sub.PIPE).communicate()
#
# print man_success[0]
# print html_success[0]
# if chown_success[1] is None:
#    print "Successfully changed owner of %s to %s" %(datapath,str(userid))
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
