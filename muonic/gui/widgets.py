"""
Provides the different physics widgets
"""
from __future__ import print_function
import datetime
import os
import time

try:
    from matplotlib.backends.backend_qt4agg \
        import NavigationToolbar2QTAgg as NavigationToolbar
except ImportError:
    from matplotlib.backends.backend_qt4agg \
        import NavigationToolbar2QT as NavigationToolbar

import numpy as np

from PyQt4 import QtGui
from PyQt4 import QtCore

from muonic.daq.provider import BaseDAQProvider
from muonic.gui.helpers import HistoryAwareLineEdit
from muonic.gui.plot_canvases import ScalarsCanvas, LifetimeCanvas
from muonic.gui.plot_canvases import PulseCanvas, PulseWidthCanvas
from muonic.gui.plot_canvases import VelocityCanvas
from muonic.gui.dialogs import DecayConfigDialog
from muonic.gui.dialogs import VelocityConfigDialog, FitRangeConfigDialog
from muonic.analysis import fit, gaussian_fit
from muonic.analysis import VelocityTrigger, DecayTriggerThorough
from muonic.util import rename_muonic_file, get_hours_from_duration
from muonic.util import get_setting, WrappedFile


class BaseWidget(QtGui.QWidget):
    """
    Base widget class

    :param logger: logger object
    :type logger: logging.Logger
    :param parent: parent widget
    """

    def __init__(self, logger, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.logger = logger
        self.parent = parent
        self._active = False

    def update(self, *args):
        """
        Update widget contents.

        :param args:
        :returns: None
        """
        QtGui.QWidget.update(*args)

    def calculate(self, *args):
        """
        Calculates data related to this widget.

        :param args:
        :returns:
        """
        pass

    def active(self, value=None):
        """
        Getter and setter for active state.

        :param value: value for the new state
        :type value: bool or None
        :returns: bool
        """
        if value is not None:
            self._active = value
        return self._active

    def start(self):
        """
        Perform setup here like resetting variables when the
        widget goes into active state

        :return: None
        """
        pass

    def stop(self):
        """
        Perform actions like saving data when the widget goes
        into inactive state

        :return:
        """
        pass

    def daq_put(self, msg):
        """
        Send message to DAQ cards. Reuses the connection of the parent widget
        if present.

        Returns True if operation was successful.

        :param msg: message to send to the DAQ card
        :type msg: str
        :returns: bool
        """
        if self.parent is None or self.parent.daq is None:
            self.logger.error("no daq handle found")
            return False

        if isinstance(self.parent.daq, BaseDAQProvider):
            self.parent.daq.put(msg)
            return True
        return False

    def daq_get_last_msg(self):
        """
        Get the last DAQ message received by the parent, if present.

        :returns: str or None
        """
        if self.parent is not None and self.parent.last_daq_msg is not None:
            return self.parent.last_daq_msg
        return None

    def finish(self):
        """
        Gets called upon closing application. Implement cleanup routines like
        closing files here.

        :returns: None
        """
        pass


class RateWidget(BaseWidget):
    """
    Widget for displaying a rate plot

    :param logger: logger object
    :type logger: logging.Logger
    :param filename: filename for the rate data file
    :type filename: str
    :param parent: parent widget
    """
    SCALAR_BUF_SIZE = 5

    def __init__(self, logger, filename, parent=None):
        BaseWidget.__init__(self, logger, parent)

        # measurement start and duration
        self.measurement_duration = datetime.timedelta()
        self.start_time = datetime.datetime.utcnow()

        # define the begin of the time interval for the rate calculation
        self.last_query_time = 0
        self.query_time = time.time()
        self.time_window = 0
        self.show_trigger = True

        # lists of channel and trigger scalars
        # 0..3: channel 0-3
        # 4:    trigger
        self.previous_scalars = self.new_scalar_buffer()
        self.scalar_buffer = self.new_scalar_buffer()
        
        # maximum and minimum seen rate across channels and trigger
        self.max_rate = 0
        self.min_rate = 0

        # we will write the column headers of the data into
        # data_file in the first run
        self.first_run = True

        # are we in first cycle after start button is pressed?
        self.first_cycle = False

        # data file options
        self.data_file = WrappedFile(filename)

        # rates store
        self.rates = None

        # initialize plot canvas
        self.scalars_monitor = ScalarsCanvas(self, logger)

        self.table = QtGui.QTableWidget(5, 2, self)
        self.table.setEnabled(False)
        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 60)
        self.table.setHorizontalHeaderLabels(["rate [1/s]", "counts"])
        self.table.setVerticalHeaderLabels(["channel 0", "channel 1", 
                                            "channel 2", "channel 3", 
                                            "trigger"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # table column fields
        self.rate_fields = dict()
        self.scalar_fields = dict()

        # add table widget items for channel and trigger values
        for i in range(self.SCALAR_BUF_SIZE):
            self.rate_fields[i] = QtGui.QTableWidgetItem('--')
            self.rate_fields[i].setFlags(QtCore.Qt.ItemIsSelectable |
                                         QtCore.Qt.ItemIsEnabled)
            self.scalar_fields[i] = QtGui.QTableWidgetItem('--')
            self.scalar_fields[i].setFlags(QtCore.Qt.ItemIsSelectable |
                                           QtCore.Qt.ItemIsEnabled)
            self.table.setItem(i, 0, self.rate_fields[i])
            self.table.setItem(i, 1, self.scalar_fields[i])

        # info fields
        self.info_fields = dict()

        # add widgets for info fields
        for key in ["start_date", "daq_time", "max_rate"]:
            self.info_fields[key] = QtGui.QLineEdit(self)
            self.info_fields[key].setReadOnly(True)
            self.info_fields[key].setDisabled(True)

        # initialize start and stop button
        self.start_button = QtGui.QPushButton('Start run')
        self.stop_button = QtGui.QPushButton('Stop run')

        QtCore.QObject.connect(self.start_button, QtCore.SIGNAL("clicked()"),
                               self.start)

        QtCore.QObject.connect(self.stop_button, QtCore.SIGNAL("clicked()"),
                               self.stop)
        self.stop_button.setEnabled(False)

        self.setup_layout()

    def new_scalar_buffer(self):
        """
        Return new zeroed list of self.SCALAR_BUF_SIZE

        :returns: list of int
        """
        return [0] * self.SCALAR_BUF_SIZE

    def setup_layout(self):
        """
        Sets up all the layout parts of the widget

        :returns: None
        """
        # create navigation toolbar
        navigation_toolbar = NavigationToolbar(self.scalars_monitor, self)

        layout = QtGui.QGridLayout(self)

        # plot layout
        plot_box = QtGui.QGroupBox("")
        plot_layout = QtGui.QGridLayout(plot_box)
        plot_layout.addWidget(self.scalars_monitor, 0, 0, 1, 2)

        # value table layout
        value_box = QtGui.QGroupBox("")
        value_box.setMaximumWidth(500)
        value_layout = QtGui.QGridLayout(value_box)
        value_layout.addWidget(self.table, 0, 0, 1, 2)
        value_layout.addWidget(QtGui.QLabel('started:'), 1, 0)
        value_layout.addWidget(self.info_fields['start_date'], 1, 1, 1, 1)
        value_layout.addWidget(QtGui.QLabel('daq time:'), 2, 0)
        value_layout.addWidget(self.info_fields['daq_time'], 2, 1)
        value_layout.addWidget(QtGui.QLabel('max rate:'), 3, 0)
        value_layout.addWidget(self.info_fields['max_rate'], 3, 1)

        # bottom line layout
        bottom_line_box = QtGui.QGroupBox("")
        bottom_line_layout = QtGui.QGridLayout(bottom_line_box)
        bottom_line_layout.addWidget(navigation_toolbar, 4, 0, 1, 3)
        bottom_line_layout.addWidget(self.start_button, 4, 3)
        bottom_line_layout.addWidget(self.stop_button, 4, 4)

        # put everything in place
        layout.addWidget(value_box, 0, 2)
        layout.addWidget(plot_box, 0, 0, 1, 2)
        layout.addWidget(bottom_line_box, 4, 0, 1, 3)

    def query_daq_for_scalars(self):
        """
        Send command to DAQ to query for scalars.

        :returns: None
        """
        self.last_query_time = self.query_time
        self.daq_put("DS")
        self.query_time = time.time()

    def extract_scalars_from_message(self, msg):
        """
        Extracts the scalar values for channel 0-3 and
        the trigger channel from daq message

        :param msg: DAQ message
        :type: str
        :return: list of ints
        """
        scalars = self.new_scalar_buffer()

        for item in msg.split():
            for i in range(self.SCALAR_BUF_SIZE):
                if item.startswith("S%d" % i) and len(item) == 11:
                    scalars[i] = int(item[3:], 16)
        return scalars

    def calculate(self):
        """
        Get the rates from the observed counts by dividing by the
        measurement interval.

        Returns True if last DAQ message was valid and could be processed.

        :returns: bool
        """
        msg = self.daq_get_last_msg()

        if not (len(msg) >= 2 and msg.startswith("DS")):
            return False

        # extract scalars from daq message
        scalars = self.extract_scalars_from_message(msg)

        # if this is the first time calculate is called, we want to set all
        # counters to zero. This is the beginning of the first bin.
        if self.first_cycle:
            self.logger.debug("Buffering muon counts for the first bin " +
                              "of the rate plot.")
            self.previous_scalars = scalars
            self.first_cycle = False
            return True

        # initialize temporary buffers for the scalar diffs
        scalar_diffs = self.new_scalar_buffer()

        # calculate differences and store current scalars for reuse
        # in the next cycle
        for i in range(self.SCALAR_BUF_SIZE):
            scalar_diffs[i] = scalars[i] - self.previous_scalars[i]
            self.previous_scalars[i] = scalars[i]

        time_window = self.query_time - self.last_query_time

        # rates for scalars of channels and trigger
        self.rates = [(_scalar / time_window) for _scalar in scalar_diffs]
        # current time window
        self.rates += [time_window]
        # scalars for channels and trigger
        self.rates += [_scalar for _scalar in scalar_diffs]

        self.time_window += time_window

        # add scalar diffs for channels and trigger to buffer
        self.scalar_buffer = [x + scalar_diffs[i]
                              for i, x in enumerate(self.scalar_buffer)]

        # get minimum and maximum rate
        min_rate = min(self.rates[:5])
        max_rate = max(self.rates[:5])

        # update minimum and maximum rate if needed
        if min_rate < self.min_rate:
            self.min_rate = min_rate
        if max_rate > self.max_rate:
            self.max_rate = max_rate

        # write the rates to data file. we have to catch IOErrors, can occur
        # if program is exited
        if self.active():
            try:
                utcdt = datetime.datetime.utcfromtimestamp(self.query_time)
                self.data_file.write(
                    "%s %f %f %f %f %f %f %f %f %f %f %f \n" %
                        (utcdt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                         self.rates[0], self.rates[1], self.rates[2],
                         self.rates[3], self.rates[4],
                         scalar_diffs[0], scalar_diffs[1],
                         scalar_diffs[2], scalar_diffs[3], scalar_diffs[4],
                         self.rates[5]))

                self.logger.debug("Rate plot data was written to %s" %
                                  repr(self.data_file))
            except ValueError:
                self.logger.warning("ValueError, Rate plot data was not " +
                                    "written to %s" % repr(self.data_file))
        return True

    def update(self):
        """
        Display newly available data

        :returns: None
        """
        if not self.active():
            return

        self.query_daq_for_scalars()

        if self.time_window == 0:
            return

        self.update_info_field("daq_time", "%.2f s" % self.time_window)
        self.update_info_field("max_rate", "%.3f 1/s" % self.max_rate)

        for i in range(4):
            self.update_fields(i, get_setting("active_ch%d" % i))
        self.update_fields(4, self.show_trigger)

        channel_config = [get_setting("active_ch%d" % i) for i in range(4)]

        self.scalars_monitor.update_plot(self.rates, self.show_trigger,
                                         channel_config)

    def update_fields(self, channel, enabled, disable_only=False):
        """
        Update table fields for a channel, channel 4 is the trigger channel.

        :param channel: the channel index
        :type channel: int
        :param enabled: enable fields
        :type enabled: bool
        :param disable_only: do not set text if 'enabled' is True
        :type disable_only: bool
        :returns: None
        """
        if channel > self.SCALAR_BUF_SIZE:
            return

        if enabled:
            if not disable_only:
                self.rate_fields[channel].setText(
                        "%.3f" % (self.scalar_buffer[channel] /
                                  self.time_window))
                self.scalar_fields[channel].setText(
                        "%d" % (self.scalar_buffer[channel]))
        else:
            self.rate_fields[channel].setText("off")
            self.scalar_fields[channel].setText("off")

    def update_info_field(self, key, text=None, enable=True):
        """
        Set text of info field with 'key' or
        trigger enable state if 'text' is None

        :param key: the key of the info field
        :type key: str
        :param text: the text to set
        :type text: str
        :param enable: enable
        :type enable: bool
        :returns: None
        """
        if text is not None:
            self.info_fields[key].setText(text)
        else:
            self.info_fields[key].setDisabled(not enable)

    def start(self):
        """
        Starts the rate measurement and opens the data file.

        :returns: None
        """
        if self.active():
            return

        self.logger.debug("Start Button Clicked")

        self.active(True)

        self.start_time = datetime.datetime.utcnow()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.table.setEnabled(True)

        time.sleep(0.2)

        self.first_cycle = True
        self.time_window = 0

        # reset scalar buffer
        self.scalar_buffer = self.new_scalar_buffer()

        # open file for writing and add comment
        self.data_file.open("a")

        # write column headers if this is the first run
        if self.first_run:
            self.data_file.write("year month day hour minutes second milliseconds" +
                                 " | R0 | R1 | R2 | R3 | R trigger | " +
                           " chan0 | chan1 | chan2 | chan3 | trigger | Delta_time\n")
            self.first_run = False

        # determine type of measurement
        if self.parent.is_widget_active("decay"):
            measurement_type = "rate+decay"
        elif self.parent.is_widget_active("velocity"):
            measurement_type = "rate+velocity"
        else:
            measurement_type = "rate"

        self.data_file.write("# new %s measurement run from: %s\n" %
                             (measurement_type,
                              self.start_time.strftime("%a %d %b %Y %H:%M:%S UTC")))

        # update table fields
        for i in range(4):
            self.update_fields(i, get_setting("active_ch%d" % i),
                               disable_only=True)

        self.update_fields(4, self.show_trigger, disable_only=True)

        # update info fields
        self.update_info_field("start_date", enable=True)
        self.update_info_field("daq_time", enable=True)
        self.update_info_field("max_rate", enable=True)

        self.update_info_field("start_date",
                               self.start_time.strftime("%d.%m.%Y %H:%M:%S"))
        self.update_info_field("daq_time", "%.2f" % self.time_window)
        self.update_info_field("max_rate", "%.2f" % self.max_rate)

        # reset plot
        self.scalars_monitor.reset(show_pending=True)

    def stop(self):
        """
        Stops the rate measurement and closes the data file.

        :returns: None
        """
        if not self.active():
            return

        self.active(False)

        stop_time = datetime.datetime.utcnow()

        self.measurement_duration += stop_time - self.start_time

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.table.setEnabled(False)

        self.update_info_field("start_date", enable=False)
        self.update_info_field("daq_time", enable=False)
        self.update_info_field("max_rate", enable=False)

        self.data_file.write("# stopped run on: %s\n" %
                             stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
        self.data_file.close()

    def finish(self):
        """
        Cleanup, close and rename data file

        :returns: None
        """
        if self.active():
            stop_time = datetime.datetime.utcnow()

            self.measurement_duration += stop_time - self.start_time

            self.data_file.write("# stopped run on: %s\n" %
                                 stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
            self.data_file.close()

        # only rename if file actually exists
        if os.path.exists(self.data_file.get_filename()):
            try:
                self.logger.info(("The rate measurement was active " +
                                  "for %f hours") %
                                 get_hours_from_duration(
                                         self.measurement_duration))
                rename_muonic_file(self.measurement_duration,
                                   self.data_file.get_filename())
            except (OSError, IOError):
                pass


class PulseAnalyzerWidget(BaseWidget):
    """
    Provides a widget which is able to show a plot of triggered pulses.

    :param logger: logger object
    :type logger: logging.Logger
    :param pulse_extractor: pulse extractor object
    :type pulse_extractor: muonic.analysis.analyzer.PulseExtractor
    :param parent: parent widget
    """
    def __init__(self, logger, pulse_extractor, parent=None):
        BaseWidget.__init__(self, logger, parent)

        self.pulses = None
        self.pulse_widths = {i : [] for i in range(4)}
        self.pulse_extractor = pulse_extractor

        # setup layout
        layout = QtGui.QGridLayout(self)

        self.checkbox = QtGui.QCheckBox(self)
        self.checkbox.setText("Show Oscilloscope and Pulse Width Distribution")
        self.checkbox.setToolTip("The oscilloscope will show the " +
                                 "last triggered pulses in the " +
                                 "selected time window")
        QtCore.QObject.connect(self.checkbox, QtCore.SIGNAL("clicked()"),
                               self.on_checkbox_clicked)

        self.pulse_width_canvases = []
        self.pulse_width_toolbars = []
        for i in range(4):
            self.pulse_width_canvases.append((PulseWidthCanvas(self, logger, 
                                                    title="Pulse Widths Ch %d"%i)))

            self.pulse_width_toolbars.append(NavigationToolbar(self.pulse_width_canvases[-1], self))

        layout.addWidget(self.checkbox, 0, 0, 1, 2)
        for i in range(4):
            cx = i/2 * 2 + 1
            cy = i%2

            layout.addWidget(self.pulse_width_canvases[i], cx, cy)
            layout.addWidget(self.pulse_width_toolbars[i], cx+1, cy)

    def calculate(self, pulses):
        """
        Calculates the pulse widths.

        :param pulses: extracted pulses
        :type pulses: list
        :returns: None
        """
        if not self.active():
            return

        self.pulses = pulses

        if self.pulses is None:
            self.logger.debug("Not received any pulses")
            return None

        # pulse_widths changed because falling edge can be None.
        # pulse_widths = [fe - le for chan in pulses[1:] for le,fe in chan]


        for i,channel in enumerate(self.pulses[1:]):
            pulse_widths = self.pulse_widths.get(i, [])
            for le, fe in channel:
                if fe is not None:
                    pulse_widths.append(fe - le)
                else:
                    pulse_widths.append(0.)
            self.pulse_widths[i] = pulse_widths
        
    def update(self):
        """
        Update plot canvases

        :returns: None
        """
        if not self.active():
            return

        #self.pulse_canvas.update_plot(self.pulses)
        for i,pwc in enumerate(self.pulse_width_canvases):
            pwc.update_plot(self.pulse_widths[i])
        self.pulse_widths = {i : [] for i in range(4)}

    def on_checkbox_clicked(self):
        """
        Starts or stops the pulse analyzer depending on checkbox state

        :returns: None
        """
        if self.checkbox.isChecked():
            self.start()
        else:
            self.stop()

    def start(self):
        """
        Starts the pulse analyzer

        :returns: None
        """
        if self.active():
            return

        self.logger.debug("switching on pulse analyzer.")
        self.active(True)

        self.daq_put("CE")

        # extract pulses to file
        self.pulse_extractor.write_pulses(True)

    def stop(self):
        """
        Stops the pulse analyzer

        :returns: None
        """
        if not self.active():
            return

        self.logger.debug("switching off pulse analyzer.")
        self.active(False)

        # stop extracting pulses to file if decay and velocity
        # measurements are inactive and global setting is also false
        if (not get_setting("write_pulses") and
                not self.parent.is_widget_active("decay") and
                not self.parent.is_widget_active("velocity")):
            self.pulse_extractor.write_pulses(False)


class StatusWidget(BaseWidget):
    """
    Provide a widget which shows the status information
    of the DAQ and the software.

    :param logger: logger object
    :type logger: logging.Logger
    :param parent: parent widget
    """
    TEXT_UNSET = "not set yet - click on Refresh."

    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)

        # setup stats
        self.daq_stats = dict()
        self.daq_stats['thresholds'] = []
        self.daq_stats['active_channels'] = []
        self.muonic_stats = dict()

        # setup daq stats
        for i in range(4):
            self.daq_stats['thresholds'].append(self.TEXT_UNSET)
            self.daq_stats['active_channels'].append(False)

        self.daq_stats['coincidences'] = self.TEXT_UNSET
        self.daq_stats['coincidence_time'] = self.TEXT_UNSET
        self.daq_stats['veto'] = self.TEXT_UNSET
        self.daq_stats['decay_veto'] = ("not set yet - start Muon " +
                                        "Decay Measurement.")

        # setup muonic stats
        self.muonic_stats['measurements'] = self.TEXT_UNSET
        self.muonic_stats['refresh_time'] = self.TEXT_UNSET
        self.muonic_stats['open_files'] = self.TEXT_UNSET
        self.muonic_stats['start_params'] = \
            "\n".join(["%s=%s" % (k, v)
                       for k, v in vars(self.parent.opts).items()])

        # setup widgets
        self.daq_widgets = dict()
        self.daq_widgets['thresholds'] = []
        self.daq_widgets['active_channels'] = []
        self.muonic_widgets = dict()

        # setup daq widgets
        for i in range(4):
            self.daq_widgets['thresholds'].append(QtGui.QLineEdit(self))
            self.daq_widgets['thresholds'][i].setReadOnly(True)
            self.daq_widgets['thresholds'][i].setText(
                    self.daq_stats['thresholds'][i])
            self.daq_widgets['thresholds'][i].setDisabled(True)

            self.daq_widgets['active_channels'].append(QtGui.QLineEdit(self))
            self.daq_widgets['active_channels'][i].setText('Channel %d' % i)
            self.daq_widgets['active_channels'][i].setReadOnly(True)
            self.daq_widgets['active_channels'][i].setEnabled(False)

        for key in ['coincidences', 'coincidence_time', 'veto', 'decay_veto']:
            self.daq_widgets[key] = QtGui.QLineEdit(self)
            self.daq_widgets[key].setReadOnly(True)
            self.daq_widgets[key].setDisabled(True)
            self.daq_widgets[key].setText(self.daq_stats[key])

        # setup muonic widgets
        for key in ['open_files', 'start_params']:
            self.muonic_widgets[key] = QtGui.QPlainTextEdit(self)
            self.muonic_widgets[key].setReadOnly(True)
            self.muonic_widgets[key].setDisabled(True)
            self.muonic_widgets[key].setPlainText(self.muonic_stats[key])

        for key in ['measurements', 'refresh_time']:
            self.muonic_widgets[key] = QtGui.QLineEdit(self)
            self.muonic_widgets[key].setReadOnly(True)
            self.muonic_widgets[key].setDisabled(True)
            self.muonic_widgets[key].setText(self.muonic_stats[key])

        layout = QtGui.QGridLayout(self)

        # add daq status widgets
        layout.addWidget(QtGui.QLabel("Status of the DAQ card:"), 0, 0)
        layout.addWidget(QtGui.QLabel("Active channels:"), 1, 0)
        layout.addWidget(QtGui.QLabel("Threshold:"), 2, 0)
        layout.addWidget(QtGui.QLabel("Trigger condition:"), 3, 0)
        layout.addWidget(QtGui.QLabel("Time window for trigger condition:"),
                         3, 3)
        layout.addWidget(QtGui.QLabel("Veto:"), 4, 0)
        layout.addWidget(QtGui.QLabel("Muon Decay Veto:"), 5, 0)

        for i in range(4):
            layout.addWidget(self.daq_widgets['active_channels'][i], 1, i + 1)
            layout.addWidget(self.daq_widgets['thresholds'][i], 2, i + 1)

        layout.addWidget(self.daq_widgets['coincidences'], 3, 1, 1, 2)
        layout.addWidget(self.daq_widgets['coincidence_time'], 3, 4)
        layout.addWidget(self.daq_widgets['veto'], 4, 1, 1, 4)
        layout.addWidget(self.daq_widgets['decay_veto'], 5, 1, 1, 4)

        # add muonic status widgets
        layout.addWidget(QtGui.QLabel(self), 6, 0)
        layout.addWidget(QtGui.QLabel("Status of Muonic:"), 7, 0)
        layout.addWidget(QtGui.QLabel("Active measurements:"), 8, 0)
        layout.addWidget(QtGui.QLabel("Measurement intervals:"), 8, 3)
        layout.addWidget(QtGui.QLabel("Start parameter:"), 9, 0)
        layout.addWidget(QtGui.QLabel("Currently opened files:"), 11, 0)
        layout.addWidget(self.muonic_widgets['measurements'], 8, 1, 1, 2)
        layout.addWidget(self.muonic_widgets['refresh_time'], 8, 4)
        layout.addWidget(self.muonic_widgets['start_params'], 9, 1, 2, 4)
        layout.addWidget(self.muonic_widgets['open_files'], 11, 1, 2, 4)

        self.refresh_button = QtGui.QPushButton("Refresh")
        self.refresh_button.setDisabled(False)
        QtCore.QObject.connect(self.refresh_button,
                               QtCore.SIGNAL("clicked()"),
                               self.on_refresh_clicked)

        layout.addWidget(self.refresh_button, 13, 0, 1, 6)

    def on_refresh_clicked(self):
        """
        Refresh the status information

        :returns: None
        """
        self.refresh_button.setDisabled(True)        
        self.logger.debug("Refreshing status information.")

        # request status information from DAQ card
        self.daq_put('TL')
        time.sleep(0.5)
        self.daq_put('DC')
        time.sleep(0.5)

        self.active(True)
        self.parent.process_incoming()

    def _update_daq_stats(self):
        """
        Gather daq status information.

        :returns: None
        """
        for i in range(4):
            self.daq_stats['active_channels'][i] = \
                get_setting("active_ch%d" % i)
            self.daq_stats['thresholds'][i] = \
                ("%d mV" % get_setting("threshold_ch%d" % i))

        if get_setting("veto"):
            for i in range(3):
                if get_setting("veto_ch%d" % i):
                    self.daq_stats['veto'] = "veto with channel %d" % i
        else:
            self.daq_stats['veto'] = 'no veto set'

        if self.parent.is_widget_active("decay"):
            self.daq_stats['decay_veto'] = \
                "software veto with channel %d" % (
                    self.parent.get_widget("decay").veto_pulse_channel - 1)
        else:
            self.daq_stats['decay_veto'] = ("not set yet - start Muon " +
                                            "Decay Measurement.")

        self.daq_stats['coincidence_time'] = ("%d ns" %
                                              get_setting("gate_width"))

        for i, value in enumerate(["Single", "Twofold", "Threefold",
                                   "Fourfold"]):
            if get_setting("coincidence%d" % i):
                self.daq_stats['coincidences'] = "%s Coincidence" % value

    def _update_muonic_stats(self):
        """
        Gather muonic status information.

        :returns: None
        """
        measurements = []

        for name, title in [("rate", "Muon Rates"),
                            ("decay", "Muon Decay"),
                            ("velocity", "Muon Velocity"),
                            ("pulse", "Pulse Analyzer")]:
            if self.parent.is_widget_active(name):
                measurements.append(title)

        self.muonic_stats['measurements'] = ", ".join(measurements)
        self.muonic_stats['refresh_time'] = ("%f s" %
                                             get_setting("time_window"))

        # since we use WrappedFile for opening file, we can
        # easily track the open files
        open_files = WrappedFile.get_open_files()

        self.muonic_stats['open_files'] = "\n".join(open_files)

    def update(self):
        """
        Fill the status information in the widget.

        :returns: None
        """
        if not self.active() or not self.isVisible():
            return

        self.logger.debug("Refreshing status infos")

        self._update_daq_stats()
        self._update_muonic_stats()

        # update daq widgets
        for i in range(4):
            self.daq_widgets['thresholds'][i].setText(
                    self.daq_stats['thresholds'][i])
            self.daq_widgets['thresholds'][i].setDisabled(False)
            self.daq_widgets['thresholds'][i].setEnabled(True)

            self.daq_widgets['active_channels'][i].setEnabled(
                    self.daq_stats['active_channels'][i])

        for key in ['coincidences', 'coincidence_time', 'veto', 'decay_veto']:
            self.daq_widgets[key].setText(
                self.daq_stats[key])
            self.daq_widgets[key].setEnabled(True)

        # update muonic widgets
        for key in ['measurements', 'refresh_time']:
            self.muonic_widgets[key].setText(self.muonic_stats[key])
            self.muonic_widgets[key].setEnabled(True)

        for key in ['start_params', 'open_files']:
            self.muonic_widgets[key].setPlainText(self.muonic_stats[key])
            self.muonic_widgets[key].setEnabled(True)

        self.refresh_button.setDisabled(False)
        self.active(False)


class VelocityWidget(BaseWidget):
    """
    Shows the muon velocity plot

    :param logger: logger object
    :type logger: logging.Logger
    :param pulse_extractor: pulse extractor object
    :type pulse_extractor: muonic.analysis.analyzer.PulseExtractor
    :param parent: parent widget
    """
    def __init__(self, logger, filename, pulse_extractor, parent=None):
        BaseWidget.__init__(self, logger, parent)

        self.pulse_extractor = pulse_extractor

        self.upper_channel = 0
        self.lower_channel = 1
        self.muon_counter = 0

        self.binning = (0., 30, 25)

        # default fit range
        self.fit_range = (self.binning[0], self.binning[1])

        self.event_data = []
        self.last_event_time = None
        self.active_since = None

        self.mu_file = WrappedFile(filename)

        # measurement duration and start time
        self.measurement_duration = datetime.timedelta()
        self.start_time = datetime.datetime.utcnow()

        # velocity canvas
        self.plot_canvas = VelocityCanvas(self, logger,
                                          binning=self.binning)

        # we want the plot canvas to fill as much space as possible
        self.plot_canvas.setSizePolicy(
                QtGui.QSizePolicy.Expanding,
                QtGui.QSizePolicy.Expanding)

        # velocity trigger
        self.trigger = VelocityTrigger(logger)

        # checkbox and buttons
        self.checkbox = QtGui.QCheckBox(self)
        self.checkbox.setText("Measure Flight Time")

        self.fit_button = QtGui.QPushButton('Fit!')
        self.fit_button.setEnabled(False)

        self.fit_range_button = QtGui.QPushButton('Fit Range')
        self.fit_range_button.setEnabled(False)

        QtCore.QObject.connect(self.checkbox,
                               QtCore.SIGNAL("clicked()"),
                               self.on_checkbox_clicked)
        QtCore.QObject.connect(self.fit_button, QtCore.SIGNAL("clicked()"),
                               self.on_fit_clicked)
        QtCore.QObject.connect(self.fit_range_button,
                               QtCore.SIGNAL("clicked()"),
                               self.on_fit_range_clicked)

        self.running_status = None
        self.muon_counter_label = QtGui.QLabel(self)
        self.last_event_label = QtGui.QLabel(self)
        self.active_since_label = QtGui.QLabel(self)

        navigation_toolbar = NavigationToolbar(self.plot_canvas, self)

        # add widgets to layout
        layout = QtGui.QGridLayout(self)
        layout.addWidget(self.checkbox, 0, 0, 1, 3)
        layout.addWidget(self.muon_counter_label, 1, 0)
        layout.addWidget(self.last_event_label, 2, 0)
        layout.addWidget(self.active_since_label, 3, 0)
        layout.addWidget(self.plot_canvas, 4, 0, 1, 3)
        layout.addWidget(navigation_toolbar, 5, 0)
        layout.addWidget(self.fit_range_button, 5, 1)
        layout.addWidget(self.fit_button, 5, 2)

    def on_fit_clicked(self):
        """
        Fit the muon velocity histogram

        :returns: None
        """
        self.logger.debug("Using fit range of %s" % repr(self.fit_range))
        fit_results = gaussian_fit(
                bincontent=np.asarray(self.plot_canvas.heights),
                binning=self.binning, fitrange=self.fit_range)

        if fit_results is not None:
            self.plot_canvas.show_fit(*fit_results)

    def on_fit_range_clicked(self):
        """
        Adjust the fit range

        :returns: None
        """
        dialog = FitRangeConfigDialog(
                upper_lim=(0., 60., self.fit_range[1]),
                lower_lim=(-1., 60., self.fit_range[0]), dimension='ns')

        if dialog.exec_() == 1:
            upper_limit = dialog.get_widget_value("upper_limit")
            lower_limit = dialog.get_widget_value("lower_limit")
            self.fit_range = (lower_limit, upper_limit)

    def on_checkbox_clicked(self):
        """
        Starts or stops detecting muons depending on checkbox state

        :returns: None
        """
        if self.checkbox.isChecked():
            self.start()
        else:
            self.stop()

    def calculate(self, pulses):
        """
        Trigger muon flight

        :param pulses: extracted pulses
        :type pulses: list
        :returns: None
        """
        if pulses is None:
            return

        flight_time = self.trigger.trigger(pulses,
                                           upper_channel=self.upper_channel,
                                           lower_channel=self.lower_channel)

        if flight_time is not None and flight_time > 0:
            self.event_data.append(flight_time)
            self.muon_counter += 1
            self.last_event_time = datetime.datetime.utcnow()
            self.logger.info("measured flight time %s" % flight_time)

    def update(self):
        """
        Update widget

        :returns: None
        """
        if not self.active() or not self.event_data:
            return

        self.fit_range_button.setEnabled(True)
        self.fit_button.setEnabled(True)
        self.plot_canvas.update_plot(self.event_data)

        self.muon_counter_label.setText("We have detected %d muons " %
                                        self.muon_counter)
        self.last_event_label.setText(
                "The last muon was detected at %s" %
                self.last_event_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
        for flight_time in self.event_data:
            self.mu_file.write("%s Flight time %s\n" % (
                self.last_event_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                repr(flight_time)))

        self.event_data = []

    def start(self):
        """
        Start detecting muons

        :returns: None
        """
        if self.active():
            return

        # launch the settings dialog
        dialog = VelocityConfigDialog()

        if dialog.exec_() == 1:
            self.checkbox.setChecked(True)
            self.muon_counter_label.setText("We have detected %d muons " %
                                            self.muon_counter)
            self.active_since = datetime.datetime.utcnow()
            self.active_since_label.setText(
                    "The measurement is active since %s" %
                    self.active_since.strftime("%a %d %b %Y %H:%M:%S UTC"))

            for chan in range(4):
                if dialog.get_widget_value("upper_checkbox_%d" % chan):
                    self.upper_channel = chan + 1  # chan index is shifted
                if dialog.get_widget_value("lower_checkbox_%d" % chan):
                    self.lower_channel = chan + 1  # chan index is shifted

            self.logger.info("Switching off decay measurement if running!")
            if self.parent.is_widget_active("decay"):
                self.parent.get_widget("decay").stop()

            self.running_status = QtGui.QLabel("Muon velocity " +
                                               "measurement active!")
            self.parent.status_bar.addPermanentWidget(self.running_status)

            self.start_time = datetime.datetime.utcnow()
            self.mu_file.open("a")
            self.mu_file.write("# new velocity measurement run from: %s\n" %
                               self.start_time.strftime("%a %d %b %Y %H:%M:%S UTC"))

            self.active(True)

            # restart rate measurement
            self.parent.get_widget("rate").stop()
            self.parent.get_widget("rate").start()

            # enable counter
            self.daq_put("CE")

            # write pulses to file
            self.pulse_extractor.write_pulses(True)
        else:
            self.logger.info("Moun velocity config canceled")
            self.active(False)
            self.checkbox.setChecked(False)
            self.active_since_label.setText("")

    def stop(self):
        """
        Stop detecting muons

        :returns: None
        """
        if not self.active():
            return

        stop_time = datetime.datetime.utcnow()
        self.measurement_duration += stop_time - self.start_time

        self.logger.info("Muon velocity mode now deactivated, returning to " +
                         "previous setting (if available)")

        self.mu_file.write("# stopped run on: %s\n" %
                           stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
        self.mu_file.close()

        # stop extracting pulses to file if pulse analyzer and decay
        # measurements are inactive and global setting is also false
        if (not get_setting("write_pulses") and
                not self.parent.is_widget_active("pulse") and
                not self.parent.is_widget_active("decay")):
            self.pulse_extractor.write_pulses(False)

        self.active(False)
        self.checkbox.setChecked(False)
        self.active_since_label.setText("")
        self.parent.status_bar.removeWidget(self.running_status)
        self.parent.get_widget("rate").stop()

    def finish(self):
        """
        Cleanup, close and rename decay file

        :returns: None
        """
        if not self.mu_file.closed:
            stop_time = datetime.datetime.utcnow()

            # add duration
            self.measurement_duration += stop_time - self.start_time

            self.mu_file.write("# stopped run on: %s\n" %
                               stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
            self.mu_file.close()

        # only rename if file actually exists
        if os.path.exists(self.mu_file.get_filename()):
            try:
                self.logger.info(("The muon velocity measurement was " +
                                  "active for %f hours") %
                                 get_hours_from_duration(
                                     self.measurement_duration))
                rename_muonic_file(self.measurement_duration,
                                   self.mu_file.get_filename())
            except (OSError, IOError):
                pass


class DecayWidget(BaseWidget):
    """
    Shows the muon decay plot

    :param logger: logger object
    :type logger: logging.Logger
    :param filename: filename for the rate data file
    :type filename: str
    :param pulse_extractor: pulse extractor object
    :type pulse_extractor: muonic.analysis.analyzer.PulseExtractor
    :param parent: parent widget
    """
    def __init__(self, logger, filename, pulse_extractor, parent=None):
        BaseWidget.__init__(self, logger, parent)

        self.pulse_extractor = pulse_extractor

        # default decay configuration
        self.min_single_pulse_width = 0
        self.max_single_pulse_width = 100000  # inf
        self.min_double_pulse_width = 0
        self.max_double_pulse_width = 100000  # inf
        self.muon_counter = 0
        self.single_pulse_channel = 0
        self.double_pulse_channel = 1
        self.veto_pulse_channel = 2
        self.decay_min_time = 0

        # ignore first bin because of after pulses,
        # see https://github.com/achim1/muonic/issues/39
        self.binning = (0, 10, 21)

        # default fit range
        self.fit_range = (1.5, 10.)

        self.event_data = []
        self.last_event_time = None
        self.active_since = None

        self.mu_file = WrappedFile(filename)

        # measurement duration and start time
        self.measurement_duration = datetime.timedelta()
        self.start_time = datetime.datetime.utcnow()

        self.previous_coinc_time_03 = "00"
        self.previous_coinc_time_02 = "0A"

        # lifetime plot canvas
        self.plot_canvas = LifetimeCanvas(self, logger)

        # we want the plot canvas to fill as much space as possible
        self.plot_canvas.setSizePolicy(
                QtGui.QSizePolicy.Expanding,
                QtGui.QSizePolicy.Expanding)

        # decay trigger
        self.trigger = DecayTriggerThorough(logger)

        # checkbox and buttons
        self.checkbox = QtGui.QCheckBox(self)
        self.checkbox.setText("Check for Decayed Muons")

        self.fit_button = QtGui.QPushButton("Fit!")
        self.fit_button.setEnabled(False)

        self.fit_range_button = QtGui.QPushButton("Fit Range")
        self.fit_range_button.setEnabled(False)

        QtCore.QObject.connect(self.checkbox,
                               QtCore.SIGNAL("clicked()"),
                               self.on_checkbox_clicked)
        QtCore.QObject.connect(self.fit_button, QtCore.SIGNAL("clicked()"),
                               self.on_fit_clicked)
        QtCore.QObject.connect(self.fit_range_button,
                               QtCore.SIGNAL("clicked()"),
                               self.on_fit_range_clicked)

        self.running_status = None
        self.muon_counter_label = QtGui.QLabel(self)
        self.last_event_label = QtGui.QLabel(self)
        self.active_since_label = QtGui.QLabel(self)

        navigation_toolbar = NavigationToolbar(self.plot_canvas, self)

        # add widgets to layout
        layout = QtGui.QGridLayout(self)
        layout.addWidget(self.checkbox, 0, 0, 1, 3)
        layout.addWidget(self.muon_counter_label, 1, 0)
        layout.addWidget(self.last_event_label, 2, 0)
        layout.addWidget(self.active_since_label, 3, 0)
        layout.addWidget(self.plot_canvas, 4, 0, 1, 3)
        layout.addWidget(navigation_toolbar, 5, 0)
        layout.addWidget(self.fit_range_button, 5, 1)
        layout.addWidget(self.fit_button, 5, 2)

    def set_previous_coincidence_times(self, time_03, time_02):
        """
        Sets the previous coincidence times obtained from the DAQ card

        :param time_03: time 03
        :type time_03: str
        :param time_02: time 03
        :type time_02: str
        :return:
        """
        self.previous_coinc_time_03 = time_03
        self.previous_coinc_time_02 = time_02

    def on_fit_clicked(self):
        """
        Fit the muon decay histogram

        :returns: None
        """
        fit_results = fit(bincontent=np.asarray(self.plot_canvas.heights),
                          binning=self.binning, fitrange=self.fit_range)

        if fit_results is not None:
            self.plot_canvas.show_fit(*fit_results)

    def on_fit_range_clicked(self):
        """
        Adjust the fit range

        :returns: None
        """
        dialog = FitRangeConfigDialog(
                upper_lim=(0., 10., self.fit_range[1]),
                lower_lim=(-1., 10., self.fit_range[0]),
                dimension='microsecond')

        if dialog.exec_() == 1:
            upper_limit = dialog.get_widget_value("upper_limit")
            lower_limit = dialog.get_widget_value("lower_limit")
            self.fit_range = (lower_limit, upper_limit)

    def on_checkbox_clicked(self):
        """
        Starts or stops the muon decay check depending on checkbox state

        :returns: None
        """
        if self.checkbox.isChecked():
            self.start()
        else:
            self.stop()

    def calculate(self, pulses):
        """
        Trigger muon decay

        :param pulses: extracted pulses
        :type pulses: list
        :returns: None
        """
        decay = self.trigger.trigger(
                pulses, single_channel=self.single_pulse_channel,
                double_channel=self.double_pulse_channel,
                veto_channel=self.veto_pulse_channel,
                min_decay_time=self.decay_min_time,
                min_single_pulse_width=self.min_single_pulse_width,
                max_single_pulse_width=self.max_single_pulse_width,
                min_double_pulse_width=self.min_double_pulse_width,
                max_double_pulse_width=self.max_double_pulse_width)

        if decay is not None:
            when = datetime.datetime.utcnow()
            self.event_data.append((decay / 1000, 
                                    when.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]))
            self.muon_counter += 1
            self.last_event_time = when
            self.logger.info("We have found a decaying muon with a " +
                             "decay time of %f at %s" % (decay, when))

    def update(self):
        """
        Update widget

        :returns: None
        """
        if not self.active() or not self.event_data:
            return

        decay_times = [decay_time[0] for decay_time in self.event_data]

        self.fit_button.setEnabled(True)
        self.fit_range_button.setEnabled(True)
        self.plot_canvas.update_plot(decay_times)

        self.muon_counter_label.setText("We have %d decayed muons " %
                                        self.muon_counter)
        self.last_event_label.setText(
                "Last detected decay at time %s " %
                self.last_event_time.strftime("%a %d %b %Y %H:%M:%S UTC"))

        for decay in self.event_data:
            decay_time = decay[1]#.replace(' ', '_')
            self.mu_file.write("%s Decay %s\n" % (repr(decay_time),
                                                  repr(decay[0])))

        self.event_data = []

    def start(self):
        """
        Start check for muon decay

        :returns: None
        """
        if self.active():
            return

        self.checkbox.setChecked(False)

        # launch the settings dialog
        dialog = DecayConfigDialog()

        if dialog.exec_() == 1:
            self.checkbox.setChecked(True)
            self.muon_counter_label.setText("We have %d decayed muons " %
                                            self.muon_counter)
            self.active_since = datetime.datetime.utcnow()
            self.active_since_label.setText(
                    "The measurement is active since %s" %
                    self.active_since.strftime("%a %d %b %Y %H:%M:%S UTC"))

            self.decay_min_time = int(
                    dialog.get_widget_value("min_pulse_time"))

            if dialog.get_widget_value("set_pulse_width_conditions"):
                self.min_single_pulse_width = int(
                        dialog.get_widget_value("min_single_pulse_width"))
                self.max_single_pulse_width = int(
                        dialog.get_widget_value("max_single_pulse_width"))
                self.min_double_pulse_width = int(
                        dialog.get_widget_value("min_double_pulse_width"))
                self.max_double_pulse_width = int(
                        dialog.get_widget_value("max_double_pulse_width"))

            for chan in range(4):
                if dialog.get_widget_value("single_checkbox_%d" % chan):
                    self.single_pulse_channel = chan + 1  # ch index is shifted
                if dialog.get_widget_value("double_checkbox_%d" % chan):
                    self.double_pulse_channel = chan + 1  # ch index is shifted
                if dialog.get_widget_value("veto_checkbox_%d" % chan):
                    self.veto_pulse_channel = chan + 1  # ch index is shifted

            self.logger.info("Switching off velocity measurement if running!")

            if self.parent.is_widget_active("decay"):
                self.parent.get_widget("velocity").stop()

            self.logger.warn("We now activate the muon decay mode!\n" +
                             "All other Coincidence/Veto settings will " +
                             "be overridden!")

            self.logger.warning("Changing gate width and enabeling pulses")
            self.logger.info("Looking for single pulse in Channel %d" %
                             (self.single_pulse_channel - 1))
            self.logger.info("Looking for double pulse in Channel %d" %
                             (self.double_pulse_channel - 1))
            self.logger.info("Using veto pulses in Channel %i" %
                             (self.veto_pulse_channel - 1))

            self.running_status = QtGui.QLabel("Muon Decay " +
                                               "measurement active!")
            self.parent.status_bar.addPermanentWidget(self.running_status)

            # configure DAQ card with coincidence/veto settings
            self.daq_put("DC")
            self.daq_put("CE")
            self.daq_put("WC 03 04")
            self.daq_put("WC 02 0A")

            # this should set the veto to none (because we have a
            # software veto) and the coincidence to single,
            # so we take all pulses
            self.daq_put("WC 00 0F")

            self.start_time = datetime.datetime.utcnow()
            self.mu_file.open("a")
            self.mu_file.write("# new decay measurement run from: %s\n" %
                               self.start_time.strftime("%a %d %b %Y %H:%M:%S UTC"))

            self.active(True)

            # restart rate measurement
            self.parent.get_widget("rate").stop()
            self.parent.get_widget("rate").start()

            # write pulses to file
            self.pulse_extractor.write_pulses(True)
        else:
            self.logger.info("Moun decay config canceled")
            self.active(False)
            self.checkbox.setChecked(False)
            self.active_since_label.setText("")

    def stop(self):
        """
        Stop check for muon decay

        :returns: None
        """
        if not self.active():
            return

        stop_time = datetime.datetime.utcnow()
        self.measurement_duration += stop_time - self.start_time

        # reset coincidence times
        self.daq_put("WC 03 " + self.previous_coinc_time_03)
        self.daq_put("WC 02 " + self.previous_coinc_time_02)

        self.logger.info("Muon decay mode now deactivated, returning to " +
                         "previous setting (if available)")

        self.mu_file.write("# stopped run on: %s\n" %
                           stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
        self.mu_file.close()

        # stop extracting pulses to file if pulse analyzer and velocity
        # measurements are inactive and global setting is also false
        if (not get_setting("write_pulses") and
                not self.parent.is_widget_active("pulse") and
                not self.parent.is_widget_active("velocity")):
            self.pulse_extractor.write_pulses(False)

        self.active(False)
        self.checkbox.setChecked(False)
        self.active_since_label.setText("")
        self.parent.status_bar.removeWidget(self.running_status)
        self.parent.get_widget("rate").stop()

    def finish(self):
        """
        Cleanup, close and rename decay file

        :returns: None
        """
        if not self.mu_file.closed:
            stop_time = datetime.datetime.utcnow()

            # add duration
            self.measurement_duration += stop_time - self.start_time

            self.mu_file.write("# stopped run on: %s\n" %
                               stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
            self.mu_file.close()

        # only rename if file actually exists
        if os.path.exists(self.mu_file.get_filename()):
            try:
                self.logger.info(("The muon decay measurement was " +
                                  "active for %f hours") %
                                 get_hours_from_duration(
                                         self.measurement_duration))
                rename_muonic_file(self.measurement_duration,
                                   self.mu_file.get_filename())
            except (OSError, IOError):
                pass


class DAQWidget(BaseWidget):
    """
    Shows the DAQ message log. The message log can be written to a file.
    This widget has a command line to issue DAQ commands.

    :param logger: logger object
    :type logger: logging.Logger
    :param filename: filename for the rate data file
    :type filename: str
    :param parent: parent widget
    """
    def __init__(self, logger, filename, parent=None):
        BaseWidget.__init__(self, logger, parent)

        # raw output file
        self.output_file = WrappedFile(filename)
        self.write_raw_file = False
        self.write_status = None

        # measurement start and duration
        self.measurement_duration = datetime.timedelta()
        self.start_time = datetime.datetime.utcnow()

        # daq msg log
        self.daq_msg_log = QtGui.QPlainTextEdit()
        self.daq_msg_log.setReadOnly(True)
        self.daq_msg_log.setFont(QtGui.QFont("monospace"))
        # 500 lines history
        self.daq_msg_log.document().setMaximumBlockCount(500)

        # input field and buttons
        self.label = QtGui.QLabel("Command")
        self.hello_edit = HistoryAwareLineEdit()
        self.file_button = QtGui.QPushButton("Save DAQ-File")

        # connect signals
        QtCore.QObject.connect(self.hello_edit,
                               QtCore.SIGNAL("returnPressed()"),
                               self.on_hello_clicked)
        QtCore.QObject.connect(self.file_button,
                               QtCore.SIGNAL("clicked()"),
                               self.on_file_clicked)

        # add widgets to layout
        layout = QtGui.QGridLayout(self)
        layout.addWidget(self.daq_msg_log, 0, 0, 1, 3)
        layout.addWidget(self.label, 1, 0)
        layout.addWidget(self.hello_edit, 1, 1)
        layout.addWidget(self.file_button, 1, 2)

    def on_hello_clicked(self):
        """
        Send a message to the DAQ card

        :returns: None
        """
        text = str(self.hello_edit.displayText())
        if len(text) > 0:
            self.daq_put(text)
            self.hello_edit.add_hist_item(text)
        self.hello_edit.clear()

    def on_file_clicked(self):
        """
        Save the raw DAQ data to a automatically named file

        :returns: None
        """
        if self.output_file.closed:
            try:
                self.file_button.setText("Stop saving DAQ-File")
                self.daq_put("CE")

                self.start_time = datetime.datetime.utcnow()
                self.output_file.open("a")
                self.output_file.write(
                        "# daq data run from: %s\n" %
                        self.start_time.strftime("%a %d %b %Y %H:%M:%S UTC"))

                self.write_status = QtGui.QLabel("Writing to %s" %
                                                 repr(self.output_file))
                self.parent.status_bar.addPermanentWidget(self.write_status)
            except IOError as e:
                self.logger.error("unable to open file '%s': %s" %
                                  (repr(self.output_file), str(e)))
        else:
            self.file_button.setText("Save DAQ-File")

            stop_time = datetime.datetime.utcnow()
            # add duration
            self.measurement_duration += stop_time - self.start_time

            self.output_file.write("# stopped run on: %s\n" %
                                   stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
            self.output_file.close()
            self.parent.status_bar.removeWidget(self.write_status)

    def update(self):
        """
        Update daq msg log

        :returns: None
        """
        msg = self.daq_get_last_msg()
        self.daq_msg_log.appendPlainText(msg)

        if not self.output_file.closed:
            self._write_to_file(msg)

    def _write_to_file(self, msg):
        """
        Write the "RAW" file

        :param msg: daq message
        :type msg: str
        :returns: None
        """
        if get_setting("write_daq_status"):
            self.output_file.write(str(msg) + "\n")
        else:
            # only write lines containing trigger data, discard status lines
            fields = msg.rstrip("\n").split(" ")
            if (len(fields) == 16) and (len(fields[0]) == 8):
                self.output_file.write(str(msg) + "\n")
            else:
                self.logger.debug(("Not writing line '%s' to file " +
                                   "because it does not contain " +
                                   "trigger data") % msg)

    def finish(self):
        """
        Cleanup, close and rename raw file

        :returns: None
        """
        if not self.output_file.closed:
            stop_time = datetime.datetime.utcnow()

            # add duration
            self.measurement_duration += stop_time - self.start_time

            self.output_file.write("# stopped run on: %s\n" %
                                   stop_time.strftime("%a %d %b %Y %H:%M:%S UTC"))
            self.output_file.close()

        # only rename if file actually exists
        if os.path.exists(self.output_file.get_filename()):
            try:
                self.logger.info("The raw data was written for %f hours" %
                                 get_hours_from_duration(
                                         self.measurement_duration))
                rename_muonic_file(self.measurement_duration,
                                   self.output_file.get_filename())
            except (OSError, IOError):
                pass


class GPSWidget(BaseWidget):
    """
    Shows GPS information

    :param logger: logger object
    :type logger: logging.Logger
    :param parent: parent widget
    """
    GPS_DUMP_LENGTH = 13

    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)

        self.gps_dump = []

        self.refresh_button = QtGui.QPushButton("Show GPS")
        QtCore.QObject.connect(self.refresh_button, QtCore.SIGNAL("clicked()"),
                               self.on_refresh_clicked)

        self.gps_status_log = QtGui.QPlainTextEdit()
        self.gps_status_log.setReadOnly(True)
        self.gps_status_log.setFont(QtGui.QFont("monospace"))
        # only 500 lines history
        self.gps_status_log.document().setMaximumBlockCount(500)

        self.status_box = QtGui.QLabel("Not read out")
        self.gps_time_box = QtGui.QLabel("--")
        self.satellites_box = QtGui.QLabel("--")
        self.checksum_box = QtGui.QLabel("--")
        self.latitude_box = QtGui.QLabel("--")
        self.longitude_box = QtGui.QLabel("--")
        self.altitude_box = QtGui.QLabel("--")
        self.pos_fix_box = QtGui.QLabel("--")

        self.msg_offset = 0

        # add widgets to layout
        layout = QtGui.QGridLayout(self)
        layout.addWidget(QtGui.QLabel("GPS Display:"), 0, 0, 1, 4)
        layout.addWidget(QtGui.QLabel("Status: "), 1, 0)
        layout.addWidget(self.status_box, 1, 1)
        layout.addWidget(QtGui.QLabel("GPS time: "), 2, 0)
        layout.addWidget(self.gps_time_box, 2, 1)
        layout.addWidget(QtGui.QLabel("#Satellites: "), 3, 0)
        layout.addWidget(self.satellites_box, 3, 1)
        layout.addWidget(QtGui.QLabel("Checksum: "), 4, 0)
        layout.addWidget(self.checksum_box, 4, 1)
        layout.addWidget(QtGui.QLabel("Latitude: "), 1, 2)
        layout.addWidget(self.latitude_box, 1, 3)
        layout.addWidget(QtGui.QLabel("Longitude: "), 2, 2)
        layout.addWidget(self.longitude_box, 2, 3)
        layout.addWidget(QtGui.QLabel("Altitude: "), 3, 2)
        layout.addWidget(self.altitude_box, 3, 3)
        layout.addWidget(QtGui.QLabel("PosFix: "), 4, 2)
        layout.addWidget(self.pos_fix_box, 4, 3)
        layout.addWidget(self.gps_status_log, 6, 0, 1, 4)
        layout.addWidget(self.refresh_button, 7, 0, 1, 4)

    def on_refresh_clicked(self):
        """
        Display/refresh the GPS information

        :returns: None
        """
        self.refresh_button.setEnabled(False)
        self.gps_dump = [] 
        self.logger.info('Reading GPS.')
        self.parent.process_incoming()
        self.active(True)
        self.daq_put('DG')
        self.parent.process_incoming()

    def _extract_gps_info(self, line, strip_string):
        """
        Extract GPS info from 'line' and strip away 'strip_string'.

        :param line: line number of gps output
        :type line: int
        :param strip_string: string to strip away
        :type strip_string: str
        :returns: str
        """
        result = str(self.gps_dump[line+self.msg_offset]).strip()
        return result.replace(strip_string, '').strip()

    def update(self):
        """
        Readout the GPS information and display it in the tab.

        :returns: bool
        """
        if len(self.gps_dump) > 0:
            if not self.gps_dump[0].startswith('DG'):
                self.gps_dump = []
                return False
        if len(self.gps_dump) <= self.GPS_DUMP_LENGTH:
            self.gps_dump.append(self.daq_get_last_msg())
        if len(self.gps_dump) != self.GPS_DUMP_LENGTH:
            return False

        # sometimes, the widget will not register the line where the DG command is put
        if not self.gps_dump[1].startswith('DG'):
            self.msg_offset = -1
	
        gps_time = ''
        pos_fix = 0
        latitude = ''
        longitude = ''
        altitude = ''
        satellites = 0
        status = "Invalid"
        checksum = "Error"

        self.refresh_button.setEnabled(True)

        try:
            if self._extract_gps_info(3, "Status:") == "A (valid)":
                status = "Valid"
                gps_time = self._extract_gps_info(2, "Date+Time:")
                pos_fix = int(self._extract_gps_info(4, "PosFix#:"))
                latitude = self._extract_gps_info(5, "Latitude:")
                longitude = self._extract_gps_info(6, "Longitude:")
                altitude = self._extract_gps_info(7, "Altitude:")
                satellites = int(self._extract_gps_info(8, "Sats used:"))

                if self._extract_gps_info(12, "ChkSumErr:") == '0':
                    checksum = "No Error"

                self.logger.info('Valid GPS signal: found %d ' % satellites)
            else:
                self.logger.info('Invalid GPS signal.')

            self.gps_dump = []
        except Exception as e:
            self.logger.warn('Error evaluating GPS information. Error %s'%str(e))
            self.gps_dump = []
            self.active(False)
            return False

        self.gps_time_box.setText(gps_time)
        self.pos_fix_box.setText(str(pos_fix))
        self.latitude_box.setText(latitude)
        self.longitude_box.setText(longitude)
        self.altitude_box.setText(altitude)
        self.satellites_box.setText(str(satellites))
        self.status_box.setText(status)
        self.checksum_box.setText(checksum)

        self.gps_status_log.appendPlainText('******************************')
        self.gps_status_log.appendPlainText('STATUS     : %s' % status)
        self.gps_status_log.appendPlainText('TIME       : %s' % gps_time)
        self.gps_status_log.appendPlainText('Altitude   : %s' % altitude)
        self.gps_status_log.appendPlainText('Latitude   : %s' % latitude)
        self.gps_status_log.appendPlainText('Longitude  : %s' % longitude)
        self.gps_status_log.appendPlainText('Satellites : %d' % satellites)
        self.gps_status_log.appendPlainText('Checksum   : %s' % checksum)
        self.gps_status_log.appendPlainText('******************************')

        self.active(False)
        return True
