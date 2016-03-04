muonic package software reference
====================================

.. default-domain:: py

main package: muonic
----------------------
.. automodule:: muonic
   :undoc-members:
   :private-members:

   :mod:`muonic.daq`
   :mod:`muonic.gui`
   :mod:`muonic.analysis`
   :mod:`muonic.util`

daq i/o with muonic.daq
-----------------------

.. automodule:: muonic.daq
   :members:
   :private-members:

`muonic.daq.provider`
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Control the two I/O threads which communicate with the DAQ. If the simulated DAQ is used, there is only one thread.

.. automodule:: muonic.daq.provider
   :members:
   :private-members:

`muonic.daq.connection`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The module provides a class which uses python-serial to open a connection over the usb ports to the daq card. Since on LINUX systems the used usb device ( which is usually /dev/tty0 ) might change during runtime, this is catched automatically by DaqConnection. Therefore a shell script is invoked.

.. automodule:: muonic.daq.connection
   :members:
   :private-members:

`muonic.daq.simulation`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This module provides a dummy class which simulates DAQ I/O which is read from the file "simdaq.txt".
The simulation is only useful if the software-gui should be tested, but no DAQ card is available

.. automodule:: muonic.daq.simulation
   :members:
   :private-members:

`muonic.daq.exceptions`
~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.daq.exceptions
   :members:
   :private-members:


pyqt4 gui with muonic.gui
-------------------------

This package contains all gui relevant classes like dialogboxes and tabwidgets. Every item in the global menu is utilizes a "Dialog" class. The "Canvas" classes contain plot routines for displaying measurements in the TabWidget.

.. automodule:: muonic.gui
   :members:
   :private-members:

`muonic.gui.application`
~~~~~~~~~~~~~~~~~~~~~~~~

Contains the  "main" gui application. It Provides the MainWindow, which initializes the different tabs and draws a menu. 


.. automodule:: muonic.gui.application
   :members:
   :private-members:

`muonic.gui.dialogs`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.gui.dialogs
   :members:
   :private-members:

`muonic.gui.helpers`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.gui.helpers
   :members:
   :private-members:

`muonic.gui.plot_canvases`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.gui.plot_canvases
   :members:
   :private-members:

`muonic.gui.widgets`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The functionality of the software

.. automodule:: muonic.gui.widgets
   :members:
   :private-members:

analyis package muonic.analysis
-------------------------------

.. automodule:: muonic.analysis
   :members:
   :private-members:

`muonic.analysis.analyzer`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Transformation of ASCII DAQ data. Combination of Pulses to events, and looking for decaying muons with different trigger condi

.. automodule:: muonic.analysis.analyzer
   :members:
   :private-members:

`muonic.analysis.fit`
~~~~~~~~~~~~~~~~~~~~~~~~~

Provide a fitting routine

.. automodule:: muonic.analysis.fit
   :members:
   :private-members:

utility package muonic.util
---------------------------
.. automodule:: muonic.util
   :members:
   :private-members:

`muonic.util.helpers`
~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.util.helpers
   :members:
   :private-members:

`muonic.util.settings_store`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.util.settings_store
   :members:
   :private-members:
