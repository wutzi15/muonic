muonic package software reference
====================================

.. default-domain:: py

main package: muonic
----------------------
.. automodule:: muonic
   :members:
   :undoc-members:
   :private-members:

   :mod:`muonic.daq`
   :mod:`muonic.gui`
   :mod:`muonic.analysis`

daq i/o with muonic.daq
-----------------------

.. automodule:: muonic.daq
   :members:
   :undoc-members:
   :private-members:

.. .. currentmodule:: muonic.daq
..   .. automethod:: __Init__ 

`muonic.daq.DAQProvider`
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Control the two I/O threads which communicate with the DAQ. If the simulated DAQ is used, there is only one thread.

.. automodule:: muonic.daq.provider
   :members:
   :undoc-members:
   :private-members:

   .. automethod:: __init__

`muonic.daq.DAQConnection`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The module provides a class which uses python-serial to open a connection over the usb ports to the daq card. Since on LINUX systems the used usb device ( which is usually /dev/tty0 ) might change during runtime, this is catched automatically by DaqConnection. Therefore a shell script is invoked.

.. automodule:: muonic.daq.connection
   :members:
   :undoc-members:
   :private-members:


`muonic.daq.DAQSimulationConnection`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This module provides a dummy class which simulates DAQ I/O which is read from the file "simdaq.txt".
The simulation is only useful if the software-gui should be tested, but no DAQ card is available

.. automodule:: muonic.daq.simulation
   :members:
   :undoc-members:
   :private-members:

pyqt4 gui with muonic.gui
-------------------------

This package contains all gui relevant classes like dialogboxes and tabwidgets. Every item in the global menu is utilizes a "Dialog" class. The "Canvas" classes contain plot routines for displaying measurements in the TabWidget.


.. automodule:: muonic.gui
   :members:

`muonic.gui.Application`
~~~~~~~~~~~~~~~~~~~~~~~~

Contains the  "main" gui application. It Provides the MainWindow, which initializes the different tabs and draws a menu. 


.. automodule:: muonic.gui.application
   :members:
   :undoc-members:
   :private-members:

`muonic.gui.widgets`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The functionality of the software



.. automodule:: muonic.gui.widgets
   :members:
   :undoc-members:
   :private-members:




`muonic.gui.dialogs`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.gui.dialogs
   :members:
   :undoc-members:
   :private-members:

`muonic.gui.plot_canvases`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: muonic.gui.plot_canvases
   :members:
   :undoc-members:
   :private-members:




analyis package muonic.analysis
-------------------------------

.. automodule:: muonic.analysis
   :members:


`muonic.analysis.analyzer`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Transformation of ASCII DAQ data. Combination of Pulses to events as well as implementation of software triggers for the muon decay and the muon velocity measurement

.. automodule:: muonic.analysis.analyzer
   :members:
   :undoc-members:
   :private-members:

`muonic.analysis.fit`
~~~~~~~~~~~~~~~~~~~~~~~~~

Provide a fitting routine

.. automodule:: muonic.analysis.fit
   :members:
   :undoc-members:
   :private-members:
