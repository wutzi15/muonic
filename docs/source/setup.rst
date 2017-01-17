muonic setup and installation
=============================

Muonic consists of two main parts:
1. the python package `muonic` 
2. a python executable

prerequesitories
-------------------

muonic needs the following packages to be installed (list may not be complete!)

* python-scipy
* python-matplotlib
* python-numpy
* python-qt4
* python-serial
* python-future

installation with pip
---------------------

Muonic can be installed using pip via

`pip install muonic`.

Pip will try to install all necessary dependencies as python packages. It can happen that all packages are already installed, e.g. as Ubuntu packages, but not in the same version as available in PyPI. In this case, pip will install the newest version from pypi. If you would like to avoid this, make sure that all dependencies are met and use
`pip install --no-deps muonic`.

installation with the setup.py script
---------------------------------------

Run the following command in the directory where you checked out the source code:

`python setup.py install`

This will install the muonic package into your python site-packages directory and also the exectuables `muonic` and `which_tty_daq` to your usr/bin directory. It also generates a new directory in your home dir: `$HOME/muonic_data`

The use of python-virtualenv is recommended.

installing muonic without the setup script
---------------------------------------------------

You just need the script `./bin/muonic` to the upper directory and rename it to `muonic.py`.
You can do this by typing

`mv bin/muonic muonic.py`

while being in the muonic main directory.

Afterwards you have to create the folder `muonic_data` in your home directory.

`mkdir ~/muonic_data`

preparing your computer to connect to the DAQ card
--------------------------------------------------

The DAQ card uses a serial connection via the USB port. If muonic does not find the DAQ card even though it is connected to the computer, try adding the user that you use for login to the group dialout:

`sudo adduser username dialout`.
