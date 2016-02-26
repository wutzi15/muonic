"""
Provide the different physics widgets
"""
import datetime
import os
import shutil
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

from muonic import DATA_PATH
from muonic.daq.provider import BaseDAQProvider
from muonic.gui.line_edit import LineEdit
from muonic.gui.plot_canvases import ScalarsCanvas, LifetimeCanvas
from muonic.gui.plot_canvases import PulseCanvas, PulseWidthCanvas
from muonic.gui.plot_canvases import VelocityCanvas
from muonic.gui.dialogs import DecayConfigDialog, PeriodicCallDialog
from muonic.gui.dialogs import VelocityConfigDialog, FitRangeConfigDialog
from muonic.analysis.fit import main as fit
from muonic.analysis.fit import gaussian_fit
from muonic.analysis.analyzer import VelocityTrigger, DecayTriggerThorough


tr = QtCore.QCoreApplication.translate


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

    def daq_get_last(self):
        """
        Get the last DAQ message received by the parent, if present.

        :returns: str or None
        """
        if self.parent is not None and self.parent.daq_msg is not None:
            return self.parent.daq_msg
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
    :param parent: parent widget
    """
    SCALAR_BUF_SIZE = 5

    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)

        # FIXME: both needed?
        # FIXME: calculate total run time in this widget, don't do that in main
        self.measurement_start = datetime.datetime.now()
        self.now = datetime.datetime.now()

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

        # are we in first cycle after start button is pressed?
        self.first_cycle = False

        # data file options
        self.data_file = None
        self.setup_data_file()

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

        self.setLayout(layout)

    def setup_data_file(self):
        """
        Write column headers to data file
        :return: None
        """
        # FIXME: take filename as argument in __init__
        with open(self.parent.filename, 'w') as f:
            f.write("chan0 | chan1 | chan2 | chan3 | " +
                    "R0 | R1 | R2 | R3 | trigger | Delta_time\n")

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
        msg = self.daq_get_last()

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
                self.data_file.write(
                        "%f %f %f %f %f %f %f %f %f %f \n" %
                        (scalar_diffs[0], scalar_diffs[1],
                         scalar_diffs[2], scalar_diffs[3],
                         self.rates[0], self.rates[1], self.rates[2],
                         self.rates[3], self.rates[4], self.rates[5]))
                self.logger.debug("Rate plot data was written to %s" %
                                  self.data_file.__repr__())
            except ValueError:
                self.logger.warning("ValueError, Rate plot data was not " +
                                    "written to %s" %
                                    self.data_file.__repr__())
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
        self.update_info_field("max_rate", "%.2f 1/s" % self.max_rate)

        # FIXME: use global settings instead of
        # FIXME: 'self.parent.channelcheckbox_0' etc...
        self.update_fields(0, self.parent.channelcheckbox_0)
        self.update_fields(1, self.parent.channelcheckbox_1)
        self.update_fields(2, self.parent.channelcheckbox_2)
        self.update_fields(3, self.parent.channelcheckbox_3)
        self.update_fields(4, self.show_trigger)

        self.scalars_monitor.update_plot(
                self.rates, self.show_trigger,
                self.parent.channelcheckbox_0, self.parent.channelcheckbox_1,
                self.parent.channelcheckbox_2, self.parent.channelcheckbox_3)

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
                        "%.2f" % (self.scalar_buffer[0] / self.time_window))
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

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.table.setEnabled(True)

        time.sleep(0.2)

        self.first_cycle = True
        self.time_window = 0

        # reset scalar buffer
        self.scalar_buffer = self.new_scalar_buffer()

        # new measurement time
        self.now = datetime.datetime.now()

        # FIXME: This does not belong here, place in corresponding widgets
        #if self.mainwindow.tab_widget.decaywidget.active:
        #    comment_file = '# new decay measurement run from: %i-%i-%i %i-%i-%i\n'\
        #                   %(date.tm_year,date.tm_mon,date.tm_mday,date.tm_hour,date.tm_min,date.tm_sec)
        #if self.mainwindow.tab_widget.velocitywidget.active:
        #    comment_file = '# new velocity measurement run from: %i-%i-%i %i-%i-%i\n'\
        #                   %(date.tm_year,date.tm_mon,date.tm_mday,date.tm_hour,date.tm_min,date.tm_sec)

        # open file for writing and add comment
        self.data_file = open(self.parent.filename, 'a')
        self.data_file.write("# new rate measurement run from: %s\n" %
                             self.now.strftime("%Y-%m-%d_%H-%M-%S"))

        # update table fields
        self.update_fields(0, self.parent.channelcheckbox_0, disable_only=True)
        self.update_fields(1, self.parent.channelcheckbox_1, disable_only=True)
        self.update_fields(2, self.parent.channelcheckbox_2, disable_only=True)
        self.update_fields(3, self.parent.channelcheckbox_3, disable_only=True)
        self.update_fields(4, self.show_trigger, disable_only=True)

        # update info fields
        self.update_info_field("start_date", enable=True)
        self.update_info_field("daq_time", enable=True)
        self.update_info_field("max_rate", enable=True)

        self.update_info_field("start_date",
                               self.now.strftime("%d.%m.%Y %H:%M:%S"))
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

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.table.setEnabled(False)

        self.update_info_field("start_date", enable=False)
        self.update_info_field("daq_time", enable=False)
        self.update_info_field("max_rate", enable=False)

        if self.data_file and not self.data_file.closed:
            date = datetime.datetime.now()
            self.data_file.write("# stopped run on: %s\n" \
                                 % date.strftime("%Y-%m-%d_%H-%M-%S"))
            self.data_file.close()


class PulseAnalyzerWidget(BaseWidget):
    """
    Provides a widget which is able to show a plot of triggered pulses.

    :param logger: logger object
    :type logger: logging.Logger
    :param parent: parent widget
    """
    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)

        self.pulses = None
        self.pulse_widths = []
        self.pulse_file = self.parent.pulseextractor.pulse_file

        # setup layout
        layout = QtGui.QGridLayout(self)

        self.checkbox = QtGui.QCheckBox(self)
        self.checkbox.setText("Show Oscilloscope and Pulse Width Distribution")
        self.checkbox.setToolTip("The oscilloscope will show the " +
                                 "last triggered pulses in the " +
                                 "selected time window")
        QtCore.QObject.connect(self.checkbox, QtCore.SIGNAL("clicked()"),
                               self.on_checkbox_clicked)

        self.pulse_canvas = PulseCanvas(self, logger)
        self.pulse_width_canvas = PulseWidthCanvas(self, logger)

        pulse_toolbar = NavigationToolbar(self.pulse_canvas, self)
        pulse_width_toolbar = NavigationToolbar(self.pulse_width_canvas, self)

        layout.addWidget(self.checkbox, 0, 0, 1, 2)
        layout.addWidget(self.pulse_canvas, 1, 0)
        layout.addWidget(pulse_toolbar, 2, 0)
        layout.addWidget(self.pulse_width_canvas, 1, 1)
        layout.addWidget(pulse_width_toolbar, 2, 1)

        self.setLayout(layout)

    def calculate(self):
        """
        Calculates the pulse widths.

        :returns: None
        """
        if not self.active():
            return

        self.pulses = self.parent.pulses

        if self.pulses is None:
            self.logger.debug("Not received any pulses")
            return None

        # pulse_widths changed because falling edge can be None.
        # pulse_widths = [fe - le for chan in pulses[1:] for le,fe in chan]

        pulse_widths = []

        for channel in self.pulses[1:]:
            for le, fe in channel:
                if fe is not None:
                    pulse_widths.append(fe - le)
                else:
                    pulse_widths.append(0.)
        self.pulse_widths += pulse_widths
        
    def update(self):
        """
        Update plot canvases

        :returns: None
        """
        if not self.active():
            return

        self.pulse_canvas.update_plot(self.pulses)
        self.pulse_width_canvas.update_plot(self.pulse_widths)
        self.pulse_widths = []

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
        self.pulse_file = self.parent.pulseextractor.pulse_file
        self.active(True)

        self.daq_put("CE")
        self.daq_put('CE')

        # FIXME: do not do this here, just add a trigger method to pulse
        # FIXME: extractor to enable or disable writing to file
        if not self.pulse_file:
            self.parent.pulsefilename = os.path.join(
                    DATA_PATH, "%s_%s_HOURS_%s" % (
                        self.parent.now.strftime('%Y-%m-%d_%H-%M-%S'), "P",
                        self.parent.opts.user))
            self.parent.pulse_mes_start = self.parent.now
            self.parent.pulseextractor.pulse_file = open(
                    self.parent.pulsefilename, 'w')
            self.logger.debug("Starting to write pulses to %s" %
                              self.parent.pulsefilename)
            self.parent.writepulses = True

    def stop(self):
        """
        Stops the pulse analyzer

        :returns: None
        """
        if not self.active():
            return

        self.logger.debug("switching off pulse analyzer.")
        self.active(False)

        # FIXME: do not do this here, just add a trigger method to pulse
        # FIXME: extractor to enable or disable writing to file
        if not self.pulse_file:
            self.parent.pulsefilename = ''
            self.parent.pulse_mes_start = False

            if self.parent.pulseextractor.pulse_file:
                self.parent.pulseextractor.pulse_file.close()
            self.parent.pulseextractor.pulse_file = False


class StatusWidget(BaseWidget): # not used yet
    """
    Provide a widget which shows the status informations of the DAQ and the muonic software
    """
    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)
        self.mainwindow = self.parentWidget()
        # more functional objects

        self.muonic_stats = dict()
        self.daq_stats = dict()

        self.daq_stats['thresholds'] = list()
        for cnt in range(4):
            self.daq_stats['thresholds'].append('not set yet - click on Refresh.')
        self.daq_stats['active_channel_0'] = None
        self.daq_stats['active_channel_1'] = None
        self.daq_stats['active_channel_2'] = None
        self.daq_stats['active_channel_3'] = None
        self.daq_stats['coincidences'] = 'not set yet - click on Refresh.'
        self.daq_stats['coincidence_timewindow'] = 'not set yet - click on Refresh.'
        self.daq_stats['veto'] = 'not set yet - click on Refresh.'

        self.muonic_stats['start_params'] = 'not set yet - click on Refresh.'
        self.muonic_stats['refreshtime'] = 'not set yet - click on Refresh.'
        self.muonic_stats['open_files'] = 'not set yet - click on Refresh.'
        self.muonic_stats['last_path'] = 'not set yet - click on Refresh.'
        self.muonic_stats['decay_veto'] = 'not set yet - start Muon Decay Measurement.'

        self.label_daq = QtGui.QLabel(tr('MainWindow','Status of the DAQ card:'))
        self.label_thresholds = QtGui.QLabel(tr('MainWindow','Threshold:'))
        self.label_active_channels = QtGui.QLabel(tr('MainWindow','Active channels:'))
        self.label_coincidences = QtGui.QLabel(tr('MainWindow','Trigger condition:'))
        self.label_coincidence_timewindow = QtGui.QLabel(tr('MainWindow','Time window for trigger condition:'))
        self.label_veto = QtGui.QLabel(tr('MainWindow','Veto:'))
        self.decay_label_veto = QtGui.QLabel(tr('MainWindow','Muon Decay Veto:'))
        self.thresholds = []
        for cnt in range(4):
            self.thresholds.append(QtGui.QLineEdit(self))
            self.thresholds[cnt].setReadOnly(True)
            self.thresholds[cnt].setText(self.daq_stats['thresholds'][cnt])
            self.thresholds[cnt].setDisabled(True)
        self.active_channel_0 = QtGui.QLineEdit(self)
        self.active_channel_1 = QtGui.QLineEdit(self)
        self.active_channel_2 = QtGui.QLineEdit(self)
        self.active_channel_3 = QtGui.QLineEdit(self)
        self.active_channel_0.setText('Channel 0')
        self.active_channel_1.setText('Channel 1')
        self.active_channel_2.setText('Channel 2')
        self.active_channel_3.setText('Channel 3')
        self.active_channel_0.setReadOnly(True)
        self.active_channel_0.setEnabled(False)
        self.active_channel_1.setReadOnly(True)
        self.active_channel_1.setEnabled(False)
        self.active_channel_2.setReadOnly(True)
        self.active_channel_2.setEnabled(False)
        self.active_channel_3.setReadOnly(True)
        self.active_channel_3.setEnabled(False)
        self.coincidences = QtGui.QLineEdit(self)
        self.coincidences.setReadOnly(True)
        self.coincidences.setDisabled(True)
        self.coincidences.setText(self.daq_stats['coincidences'])
        self.coincidence_timewindow = QtGui.QLineEdit(self)
        self.coincidence_timewindow.setReadOnly(True)
        self.coincidence_timewindow.setDisabled(True)
        self.coincidence_timewindow.setText(self.daq_stats['coincidence_timewindow'])
        self.veto = QtGui.QLineEdit(self)
        self.veto.setReadOnly(True)
        self.veto.setDisabled(True)
        self.veto.setText(self.daq_stats['veto'])
        self.decay_veto = QtGui.QLineEdit(self)
        self.decay_veto.setReadOnly(True)
        self.decay_veto.setDisabled(True)
        self.decay_veto.setText(self.muonic_stats['decay_veto'])

        self.label_muonic = QtGui.QLabel(tr('MainWindow','Status of Muonic:'))
        self.label_measurements = QtGui.QLabel(tr('MainWindow','Active measurements:'))
        self.label_start_params = QtGui.QLabel(tr('MainWindow','Start parameter:'))
        self.label_refreshtime = QtGui.QLabel(tr('MainWindow','Measurement intervals:'))
        self.label_open_files = QtGui.QLabel(tr('MainWindow','Currently opened files:'))
        self.label_last_path = QtGui.QLabel(tr('MainWindow','Last saved files:'))
        self.start_params = QtGui.QPlainTextEdit()
        self.start_params.setReadOnly(True)
        self.start_params.setDisabled(True)
        self.start_params.document().setMaximumBlockCount(10)
        self.measurements = QtGui.QLineEdit(self)
        self.measurements.setReadOnly(True)
        self.measurements.setDisabled(True)
        self.start_params.setPlainText(self.muonic_stats['start_params'])
        self.refreshtime = QtGui.QLineEdit(self)
        self.refreshtime.setReadOnly(True)
        self.refreshtime.setDisabled(True)
        self.refreshtime.setText(self.muonic_stats['refreshtime'])

        self.open_files = QtGui.QPlainTextEdit()
        self.open_files.setReadOnly(True)
        self.open_files.setDisabled(True)
        self.open_files.setPlainText(self.muonic_stats['open_files'])
        self.open_files.document().setMaximumBlockCount(10)
        #self.last_path = QtGui.QLineEdit(self)
        #self.last_path.setReadOnly(True)
        #self.last_path.setDisabled(True)
        #self.last_path.setText(self.muonic_stats['last_path'])

        self.refresh_button  = QtGui.QPushButton(tr('MainWindow','Refresh'))
        self.refresh_button.setDisabled(True)
        QtCore.QObject.connect(self.refresh_button,
                              QtCore.SIGNAL("clicked()"),
                              self.on_refresh_clicked
                              )

        self.save_button  = QtGui.QPushButton(tr('MainWindow','Save to file'))
        QtCore.QObject.connect(self.save_button,
                              QtCore.SIGNAL("clicked()"),
                              self.on_save_clicked
                              )

        status_layout = QtGui.QGridLayout(self)
        status_layout.addWidget(self.label_daq,0,0)
        status_layout.addWidget(self.label_active_channels,1,0)
        status_layout.addWidget(self.active_channel_0,1,1)
        status_layout.addWidget(self.active_channel_1,1,2)
        status_layout.addWidget(self.active_channel_2,1,3)
        status_layout.addWidget(self.active_channel_3,1,4)
        status_layout.addWidget(self.thresholds[0],2,1)
        status_layout.addWidget(self.label_thresholds,2,0)
        status_layout.addWidget(self.thresholds[1],2,2)
        status_layout.addWidget(self.thresholds[2],2,3)
        status_layout.addWidget(self.thresholds[3],2,4)
        status_layout.addWidget(self.label_coincidences,3,0)
        status_layout.addWidget(self.coincidences,3,1,1,2)
        status_layout.addWidget(self.label_coincidence_timewindow,3,3)
        status_layout.addWidget(self.coincidence_timewindow,3,4)
        status_layout.addWidget(self.label_veto,4,0)
        status_layout.addWidget(self.veto,4,1,1,4)
        status_layout.addWidget(self.decay_label_veto,5,0)
        status_layout.addWidget(self.decay_veto,5,1,1,4)
        nix = QtGui.QLabel(self)        
        status_layout.addWidget(nix,6,0)
        status_layout.addWidget(self.label_muonic,7,0)
        status_layout.addWidget(self.label_measurements,8,0)
        status_layout.addWidget(self.measurements,8,1,1,2)
        status_layout.addWidget(self.label_refreshtime,8,3)
        status_layout.addWidget(self.refreshtime,8,4)
        status_layout.addWidget(self.label_start_params,9,0)
        status_layout.addWidget(self.start_params,9,1,2,4)
        status_layout.addWidget(self.label_open_files,11,0)
        status_layout.addWidget(self.open_files,11,1,2,4)
        #status_layout.addWidget(self.label_last_path,11,1)
        #status_layout.addWidget(self.last_path,11,2,1,8)

        status_layout.addWidget(self.refresh_button,13,0,1,6)
        #status_layout.addWidget(self.save_button,11,2,1,2)

    def on_refresh_clicked(self):
        """
        Refresh the status information
        """
        self.refresh_button.setDisabled(True)        
        self.logger.debug("Refreshing status information.")
        self.mainwindow.daq.put('TL')
        time.sleep(0.5)
        self.mainwindow.daq.put('DC')
        time.sleep(0.5)
        self.active(True)
        self.mainwindow.process_incoming()

    def on_save_clicked(self):
        """
        Refresh the status information
        """
        self.logger.debug("Saving status information to file.")
        self.logger.warning('Currently not available!')


    def update(self):
        """
        Fill the status information in the widget.
        """
        self.logger.debug("Refreshing status infos")
        if (self.mainwindow.tab_widget.statuswidget.isVisible()):
            self.muonic_stats['start_params'] = str(self.mainwindow.opts).replace('{', '').replace('}','')
            self.muonic_stats['refreshtime'] = str(self.mainwindow.timewindow)+ ' s'
            self.muonic_stats['last_path'] = 'too'
            if self.mainwindow.tab_widget.decaywidget.active:
                self.muonic_stats['decay_veto'] =\
                    'software veto with channel %d' % (self.mainwindow.tab_widget.decaywidget.vetopulsechannel-1)
            
            self.daq_stats['thresholds'][0] = str(self.mainwindow.threshold_ch0)+ ' mV'
            self.daq_stats['thresholds'][1] = str(self.mainwindow.threshold_ch1)+ ' mV'
            self.daq_stats['thresholds'][2] = str(self.mainwindow.threshold_ch2)+ ' mV'
            self.daq_stats['thresholds'][3] = str(self.mainwindow.threshold_ch3)+ ' mV'
            if not self.mainwindow.vetocheckbox:
                self.daq_stats['veto'] = 'no veto set'
            else:
                if self.mainwindow.vetocheckbox_0:
                    self.daq_stats['veto'] = 'veto with channel 0'
                if self.mainwindow.vetocheckbox_1:
                    self.daq_stats['veto'] = 'veto with channel 1'
                if self.mainwindow.vetocheckbox_2:
                    self.daq_stats['veto'] = 'veto with channel 2'

            self.daq_stats['coincidence_timewindow'] = str(self.mainwindow.coincidence_time) + ' ns'

            self.daq_stats['active_channel_0'] = self.mainwindow.channelcheckbox_0
            self.daq_stats['active_channel_1'] = self.mainwindow.channelcheckbox_1
            self.daq_stats['active_channel_2'] = self.mainwindow.channelcheckbox_2
            self.daq_stats['active_channel_3'] = self.mainwindow.channelcheckbox_3
            if self.mainwindow.coincidencecheckbox_0:
                self.daq_stats['coincidences'] = 'Single Coincidence.'
            elif self.mainwindow.coincidencecheckbox_1:
                self.daq_stats['coincidences'] = 'Twofold Coincidence.'
            elif self.mainwindow.coincidencecheckbox_2:
                self.daq_stats['coincidences'] = 'Threefold Coincidence.'
            elif self.mainwindow.coincidencecheckbox_3:
                self.daq_stats['coincidences'] = 'Fourfold Coincidence.'

            for cnt in range(4):
                self.thresholds[cnt].setDisabled(False)                
                self.thresholds[cnt].setText(self.daq_stats['thresholds'][cnt])
                self.thresholds[cnt].setEnabled(True)

            self.active_channel_0.setEnabled(self.daq_stats['active_channel_0'])
            self.active_channel_1.setEnabled(self.daq_stats['active_channel_1'])
            self.active_channel_2.setEnabled(self.daq_stats['active_channel_2'])
            self.active_channel_3.setEnabled(self.daq_stats['active_channel_3'])
            self.coincidences.setText(self.daq_stats['coincidences'])
            self.coincidences.setEnabled(True)
            self.coincidence_timewindow.setText(self.daq_stats['coincidence_timewindow'])
            self.coincidence_timewindow.setEnabled(True)
            self.veto.setText(self.daq_stats['veto'])
            self.veto.setEnabled(True)
            self.decay_veto.setText(self.muonic_stats['decay_veto'])
            self.decay_veto.setEnabled(True)
            
            self.muonic_stats['open_files'] = str(self.mainwindow.filename)
            if self.mainwindow.tab_widget.daqwidget.write_file:
                self.muonic_stats['open_files'] += ', ' + self.mainwindow.rawfilename
            if self.mainwindow.tab_widget.decaywidget.active:
                self.muonic_stats['open_files'] += ', ' + self.mainwindow.decayfilename
            if self.mainwindow.writepulses:
                self.muonic_stats['open_files'] += ', ' + self.mainwindow.pulsefilename
            self.start_params.setPlainText(self.muonic_stats['start_params'])
            self.start_params.setEnabled(True)
            self.refreshtime.setText(self.muonic_stats['refreshtime'])
            self.refreshtime.setEnabled(True)
            self.open_files.setPlainText(self.muonic_stats['open_files'])
            self.open_files.setEnabled(True)
            #self.last_path.setText(self.muonic_stats['last_path'])
            #self.last_path.setEnabled(True)
            measurements = ''
            if self.mainwindow.tab_widget.ratewidget.active():
                measurements += 'Muon Rates'
            if self.mainwindow.tab_widget.decaywidget.active:
                if len(measurements) > 0:
                    measurements += ', '
                measurements += 'Muon Decay'
                self.decay_veto.setText(self.muonic_stats['decay_veto'])
            if self.mainwindow.tab_widget.velocitywidget.active:
                if len(measurements) > 0:
                    measurements += ', '
                measurements += 'Muon Velocity'
            if self.mainwindow.tab_widget.pulseanalyzerwidget.active:
                if len(measurements) > 0:
                    measurements += ', '
                measurements += 'Pulse Analyzer' 
            self.measurements.setText(measurements)
            self.measurements.setEnabled(True)
            self.start_params.setEnabled(True)

            self.active(False)
        else:
            self.logger.debug("Status informations widget not active - ignoring update call.")
        self.refresh_button.setDisabled(False)
        self.active(False)

        #FIXME: status widget has no pulsefile!
        #if not self.pulsefile:
        #    self.mainwindow.pulsefilename = ''
        #    self.mainwindow.pulse_mes_start = False
        #    if self.mainwindow.pulseextractor.pulse_file:
        #        self.mainwindow.pulseextractor.pulse_file.close()
        #    self.mainwindow.pulseextractor.pulse_file = False



class VelocityWidget(BaseWidget):

    def __init__(self,logger,parent=None):
        BaseWidget.__init__(self, logger, parent)
        self.mainwindow = self.parentWidget()
        self.upper_channel = 0
        self.lower_channel = 1
        self.trigger = VelocityTrigger(logger)
        self.times = []
        self.binning = (0.,30,25)
        self.fitrange = (self.binning[0],self.binning[1])

        self.activateVelocity = QtGui.QCheckBox(self)
        self.activateVelocity.setText(tr("Dialog", "Measure Flight Time", None, QtGui.QApplication.UnicodeUTF8))
        self.activateVelocity.setObjectName("activate_velocity")
        self.velocityfit_button = QtGui.QPushButton(tr('MainWindow', 'Fit!')) 
        self.velocityfitrange_button = QtGui.QPushButton(tr('MainWindow', 'Fit Range')) 
        displayMuons                 = QtGui.QLabel(self)
        displayMuons.setObjectName("muoncounter")
        self.muon_counter = 0
        lastdecay = QtGui.QLabel(self)
        lastdecay.setObjectName("lastdecay")
        self.last_muon = None
        activesince = QtGui.QLabel(self)
        activesince.setObjectName("activesince")
        self.active_since = None
        layout = QtGui.QGridLayout(self)
        layout.addWidget(self.activateVelocity,0,0,1,3)
        layout.addWidget(displayMuons, 1,0)
        layout.addWidget(lastdecay, 2,0)
        layout.addWidget(activesince, 3,0)
        self.findChild(QtGui.QLabel,QtCore.QString("muoncounter")).setText(tr("Dialog", "We have detected %d muons "%self.muon_counter ,None, QtGui.QApplication.UnicodeUTF8))
        self.velocitycanvas = VelocityCanvas(self,logger,binning = self.binning)
        self.velocitycanvas.setObjectName("velocity_plot")
        layout.addWidget(self.velocitycanvas,4,0,1,3)
        ntb = NavigationToolbar(self.velocitycanvas, self)
        layout.addWidget(ntb,5,0)
        layout.addWidget(self.velocityfitrange_button,5,1)
        layout.addWidget(self.velocityfit_button,5,2)
        self.velocityfitrange_button.setEnabled(False)
        self.velocityfit_button.setEnabled(False)
        QtCore.QObject.connect(self.activateVelocity,
                               QtCore.SIGNAL("clicked()"),
                               self.activateVelocityClicked
                               )
        
        QtCore.QObject.connect(self.velocityfit_button,
                              QtCore.SIGNAL("clicked()"),
                              self.velocityFitClicked
                              )

        QtCore.QObject.connect(self.velocityfitrange_button,
                              QtCore.SIGNAL("clicked()"),
                              self.velocityFitRangeClicked
                              )
        self.pulsefile = self.mainwindow.pulseextractor.pulse_file
        
    def calculate(self):
        pulses = self.mainwindow.pulses
        if pulses is None:
            return
        flighttime = self.trigger.trigger(pulses,upper_channel=self.upper_channel,lower_channel=self.lower_channel)
        if flighttime != None and flighttime > 0:
            #velocity = (self.channel_distance/((10**(-9))*flighttime))/C #flighttime is in ns, return in fractions of C
            self.logger.info("measured flighttime %s" %flighttime.__repr__())
            self.times.append(flighttime)
            self.last_muon = datetime.datetime.now()
            self.muon_counter += 1

    #FIXME: we should not name this update since update is already a member
    def update(self):
        self.velocityfitrange_button.setEnabled(True)    
        self.velocityfit_button.setEnabled(True)
        self.findChild(VelocityCanvas,QtCore.QString("velocity_plot")).update_plot(self.times)
        self.times = []
        self.findChild(QtGui.QLabel,QtCore.QString("muoncounter")).setText(tr("Dialog", "We have detected %d muons "%self.muon_counter ,None, QtGui.QApplication.UnicodeUTF8))
        self.findChild(QtGui.QLabel,QtCore.QString("lastdecay")).setText(tr("Dialog", "The last muon was detected at %s"%self.last_muon.strftime('%Y-%m-%d %H:%M:%S') ,None, QtGui.QApplication.UnicodeUTF8))

    def velocityFitRangeClicked(self):
        """
        fit the muon velocity histogram
        """
        config_dialog = FitRangeConfigDialog(
            upper_lim= (0., 60., self.fitrange[1]), lower_lim= (-1., 60., self.fitrange[0]), dimension ='ns')
        rv = config_dialog.exec_()
        if rv == 1:
            upper_limit  = config_dialog.get_widget_value("upper_limit")
            lower_limit  = config_dialog.get_widget_value("lower_limit")
            self.fitrange = (lower_limit,upper_limit)

    def velocityFitClicked(self):
        """
        fit the muon velocity histogram
        """
        self.logger.debug("Using fitrange of %s" %self.fitrange.__repr__())
        fitresults = gaussian_fit(bincontent=np.asarray(self.velocitycanvas.heights), binning = self.binning, fitrange = self.fitrange)
        if not fitresults is None:
            self.velocitycanvas.show_fit(fitresults[0],fitresults[1],fitresults[2],fitresults[3],fitresults[4],fitresults[5],fitresults[6],fitresults[7])


    def activateVelocityClicked(self):
        """
        Perform extra actions when the checkbox is clicked
        """
        if not self.active():
            config_dialog = VelocityConfigDialog()
            rv = config_dialog.exec_()
            if rv == 1:
                self.activateVelocity.setChecked(True)
                self.active_since = datetime.datetime.now()
                self.findChild(QtGui.QLabel,QtCore.QString("activesince")).setText(tr("Dialog", "The measurement is active since %s"%self.active_since.strftime('%Y-%m-%d %H:%M:%S') ,None, QtGui.QApplication.UnicodeUTF8))

                for chan,ch_label in enumerate(["0","1","2","3"]):
                    if config_dialog.get_widget_value("upper_checkbox_" + ch_label):
                        self.upper_channel = chan + 1 # ch index is shifted
                        
                for chan,ch_label in enumerate(["0","1","2","3"]):
                    if config_dialog.get_widget_value("lower_checkbox_" + ch_label):
                        self.lower_channel = chan + 1 #
            
                self.logger.info("Switching off decay measurement if running!")
                if self.parentWidget().parentWidget().decaywidget.active:
                    self.parentWidget().parentWidget().decaywidget.activateMuondecayClicked()
                self.active(True)
                self.parentWidget().parentWidget().parentWidget().daq.put("CE")
                self.parentWidget().parentWidget().ratewidget.on_start_clicked()
                if not self.pulsefile:
                    self.mainwindow.pulsefilename = \
                            os.path.join(DATA_PATH,"%s_%s_HOURS_%s%s" %(self.mainwindow.now.strftime('%Y-%m-%d_%H-%M-%S'),
                                                                       "P",
                                                                       self.mainwindow.opts.user[0],
                                                                       self.mainwindow.opts.user[1]) )
                    self.mainwindow.pulse_mes_start = self.mainwindow.now
                    self.mainwindow.pulseextractor.pulse_file = open(self.mainwindow.pulsefilename,'w')
                    self.logger.debug("Starting to write pulses to %s" %self.mainwindow.pulsefilename)
                    self.mainwindow.writepulses = True


            else:
                self.activateVelocity.setChecked(False)
                self.active(False)
                self.findChild(QtGui.QLabel,QtCore.QString("activesince")).setText(tr("Dialog", "" ,None, QtGui.QApplication.UnicodeUTF8))
        else:
            self.activateVelocity.setChecked(False)            
            self.active(False)
            self.findChild(QtGui.QLabel,QtCore.QString("activesince")).setText(tr("Dialog", "" ,None, QtGui.QApplication.UnicodeUTF8))
            if not self.pulsefile:
                self.mainwindow.pulsefilename = ''
                self.mainwindow.pulse_mes_start = False
                if self.mainwindow.pulseextractor.pulse_file:
                    self.mainwindow.pulseextractor.pulse_file.close()
                self.mainwindow.pulseextractor.pulse_file = False

            self.mainwindow.tab_widget.ratewidget.stop()


class DecayWidget(BaseWidget):
    
    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)
        self.logger = logger
        self.mufit_button = QtGui.QPushButton(tr('MainWindow', 'Fit!'))
        self.mainwindow = self.parentWidget()        
        self.mufit_button.setEnabled(False)
        self.decayfitrange_button = QtGui.QPushButton(tr('MainWindow', 'Fit Range')) 
        self.decayfitrange_button.setEnabled(False)
        self.lifetime_monitor = LifetimeCanvas(self,logger)
        self.minsinglepulsewidth = 0
        self.maxsinglepulsewidth = 100000 #inf
        self.mindoublepulsewidth = 0
        self.maxdoublepulsewidth = 100000 #inf
        self.muondecaycounter    = 0
        self.lastdecaytime       = 'None'
        self.pulsefile = self.parentWidget().pulseextractor.pulse_file
            
        self.singlepulsechannel  = 0
        self.doublepulsechannel  = 1
        self.vetopulsechannel    = 2 
        self.decay_mintime       = 0
        self.active(False)
        self.trigger             = DecayTriggerThorough(logger)
        self.decay               = []
        self.mu_file             = open("/dev/null","w") 
        self.dec_mes_start       = None
        self.previous_coinc_time_03 = "00"
        self.previous_coinc_time_02 = "0A"
        self.binning = (0,10,21)
        self.fitrange = (1.5,10.) # ignore first bin because of afterpulses, 
                                  # see https://github.com/achim1/muonic/issues/39 

        QtCore.QObject.connect(self.mufit_button,
                              QtCore.SIGNAL("clicked()"),
                              self.mufitClicked
                              )
        QtCore.QObject.connect(self.decayfitrange_button,
                              QtCore.SIGNAL("clicked()"),
                              self.decayFitRangeClicked
                              )

        ntb1 = NavigationToolbar(self.lifetime_monitor, self)

        # activate Muondecay mode with a checkbox
        self.activateMuondecay = QtGui.QCheckBox(self)
        self.activateMuondecay.setObjectName("activate_mudecay")
        self.activateMuondecay.setText(tr("Dialog", "Check for Decayed Muons", None, QtGui.QApplication.UnicodeUTF8))
        QtCore.QObject.connect(self.activateMuondecay,
                              QtCore.SIGNAL("clicked()"),
                              self.activateMuondecayClicked
                              )
        displayMuons                 = QtGui.QLabel(self)
        displayMuons.setObjectName("muoncounter")
        lastDecay                    = QtGui.QLabel(self)
        lastDecay.setObjectName("lastdecay")
        activesince = QtGui.QLabel(self)
        activesince.setObjectName("activesince")
        self.active_since = None
 
        decay_tab = QtGui.QGridLayout(self)
        decay_tab.addWidget(self.activateMuondecay,0,0)
        decay_tab.addWidget(displayMuons,1,0)
        decay_tab.addWidget(lastDecay,2,0)
        decay_tab.addWidget(activesince, 3,0)
        decay_tab.addWidget(self.lifetime_monitor,4,0,1,2)
        decay_tab.addWidget(ntb1,5,0)
        decay_tab.addWidget(self.mufit_button,5,2)
        decay_tab.addWidget(self.decayfitrange_button,5,1)
        self.findChild(QtGui.QLabel,QtCore.QString("muoncounter")).setText(tr("Dialog", "We have %i decayed muons " %self.muondecaycounter, None, QtGui.QApplication.UnicodeUTF8))
        #self.findChild(QtGui.QLabel,QtCore.QString("lastdecay")).setText(tr("Dialog", "Last detected decay at time %s " %self.lastdecaytime, None, QtGui.QApplication.UnicodeUTF8))
        #self.decaywidget = self.widget(1)

    def calculate(self):
        pulses = self.mainwindow.pulses
        #single_channel = self.singlepulsechannel, double_channel = self.doublepulsechannel, veto_channel = self.vetopulsechannel,mindecaytime = self.decay_mintime,minsinglepulsewidth = minsinglepulsewidth,maxsinglepulsewidth = maxsinglepulsewidth, mindoublepulsewidth = mindoublepulsewidth, maxdoublepulsewidth = maxdoublepulsewidth):
        decay =  self.trigger.trigger(pulses, single_channel = self.singlepulsechannel, double_channel = self.doublepulsechannel, veto_channel = self.vetopulsechannel, min_decay_time= self.decay_mintime,
                                      min_single_pulse_width= self.minsinglepulsewidth, max_single_pulse_width= self.maxsinglepulsewidth, min_double_pulse_width= self.mindoublepulsewidth, max_double_pulse_width= self.maxdoublepulsewidth)
        if decay != None:
            when = time.asctime()
            self.decay.append((decay/1000,when))
            #devide by 1000 to get microseconds
            
            self.logger.info('We have found a decaying muon with a decaytime of %f at %s' %(decay,when)) 
            self.muondecaycounter += 1
            self.lastdecaytime = when
      
    def mufitClicked(self):
        """
        fit the muon decay histogram
        """
        fitresults = fit(bincontent=np.asarray(self.lifetime_monitor.heights), binning = self.binning, fitrange = self.fitrange)
        if not fitresults is None:
            self.lifetime_monitor.show_fit(fitresults[0],fitresults[1],\
                                           fitresults[2],fitresults[3],\
                                           fitresults[4],fitresults[5],\
                                           fitresults[6],fitresults[7])

    def update(self):
        if not self.decay:
            return

        self.mufit_button.setEnabled(True)
        self.decayfitrange_button.setEnabled(True)

        decay_times =  [decay_time[0] for decay_time in self.decay]
        self.lifetime_monitor.update_plot(decay_times)
        self.findChild(QtGui.QLabel,QtCore.QString("muoncounter")).setText(tr("Dialog", "We have %i decayed muons " %self.muondecaycounter, None, QtGui.QApplication.UnicodeUTF8))
        self.findChild(QtGui.QLabel,QtCore.QString("lastdecay")).setText(tr("Dialog", "Last detected decay at time %s " %self.lastdecaytime, None, QtGui.QApplication.UnicodeUTF8))
        for muondecay in self.decay:
            #muondecay = self.decay[0]
            muondecay_time = muondecay[1].replace(' ','_')
            self.mu_file.write('Decay ')
            self.mu_file.write(muondecay_time.__repr__() + ' ')
            self.mu_file.write(muondecay[0].__repr__())
            self.mu_file.write('\n')
            self.decay = []


    def decayFitRangeClicked(self):
        """
        fit the muon decay histogram
        """
        config_dialog = FitRangeConfigDialog(
            upper_lim= (0., 10., self.fitrange[1]), lower_lim= (-1., 10., self.fitrange[0]), dimension ='microsecond')
        rv = config_dialog.exec_()
        if rv == 1:
            upper_limit  = config_dialog.get_widget_value("upper_limit")
            lower_limit  = config_dialog.get_widget_value("lower_limit")
            self.fitrange = (lower_limit,upper_limit)

    def activateMuondecayClicked(self):
        """
        What should be done if we are looking for mu-decays?
        """
 
        now = datetime.datetime.now()
        #if not self.mainwindow.mudecaymode:
        if not self.active():
                self.activateMuondecay.setChecked(False)
                # launch the settings window
                config_window = DecayConfigDialog()
                rv = config_window.exec_()
                if rv == 1:
                    self.activateMuondecay.setChecked(True)
                    self.active_since = datetime.datetime.now()
                    chan0_single = config_window.get_widget_value("single_checkbox_0")
                    chan1_single = config_window.get_widget_value("single_checkbox_1")
                    chan2_single = config_window.get_widget_value("single_checkbox_2")
                    chan3_single = config_window.get_widget_value("single_checkbox_3")
                    chan0_double = config_window.get_widget_value("double_checkbox_0")
                    chan1_double = config_window.get_widget_value("double_checkbox_1")
                    chan2_double = config_window.get_widget_value("double_checkbox_2")
                    chan3_double = config_window.get_widget_value("double_checkbox_3")
                    chan0_veto   = config_window.get_widget_value("veto_checkbox_0")
                    chan1_veto   = config_window.get_widget_value("veto_checkbox_1")
                    chan2_veto   = config_window.get_widget_value("veto_checkbox_2")
                    chan3_veto   = config_window.get_widget_value("veto_checkbox_3")
                    self.decay_mintime   = int(config_window.get_widget_value("min_pulse_time"))
                    if config_window.get_widget_value("set_pulse_width_conditions"):
                        self.minsinglepulsewidth = int(config_window.get_widget_value("min_single_pulse_width"))
                        self.maxsinglepulsewidth = int(config_window.get_widget_value("max_single_pulse_width"))
                        self.mindoublepulsewidth = int(config_window.get_widget_value("min_double_pulse_width"))
                        self.maxdoublepulsewidth = int(config_window.get_widget_value("max_double_pulse_width"))
                    
                    self.findChild(QtGui.QLabel,QtCore.QString("activesince")).setText(tr("Dialog", "The measurement is active since %s"%self.active_since.strftime('%Y-%m-%d %H:%M:%S') ,None, QtGui.QApplication.UnicodeUTF8))
                    for channel in enumerate([chan0_single,chan1_single,chan2_single,chan3_single]):
                        if channel[1]:
                            self.singlepulsechannel = channel[0] + 1 # there is a mapping later from this to an index with an offset
                # FIXME! 
                    for channel in enumerate([chan0_double,chan1_double,chan2_double,chan3_double]):
                        if channel[1]:
                            self.doublepulsechannel = channel[0] + 1 # there is a mapping later from this to an index with an offset

                    for channel in enumerate([chan0_veto,chan1_veto,chan2_veto,chan3_veto]):
                        if channel[1]:
                            self.vetopulsechannel = channel[0] + 1 # there is a mapping later from this to an index with an offset
                    self.logger.info("Switching off velocity measurement if running!")
                    if self.parentWidget().parentWidget().velocitywidget.active:
                        self.parentWidget().parentWidget().velocitywidget.activateVelocityClicked()

                    self.logger.warn("We now activate the Muondecay mode!\n All other Coincidence/Veto settings will be overriden!")

                    self.logger.warning("Changing gate width and enabeling pulses") 
                    self.logger.info("Looking for single pulse in Channel %i" %(self.singlepulsechannel - 1))
                    self.logger.info("Looking for double pulse in Channel %i" %(self.doublepulsechannel - 1 ))
                    self.logger.info("Using veto pulses in Channel %i"        %(self.vetopulsechannel - 1 ))

                    self.mu_label = QtGui.QLabel(tr('MainWindow','Muon Decay measurement active!'))
                    self.parentWidget().parentWidget().parentWidget().statusbar.addPermanentWidget(self.mu_label)

                    self.parentWidget().parentWidget().parentWidget().daq.put("DC")

                    self.parentWidget().parentWidget().parentWidget().daq.put("CE") 
                    self.parentWidget().parentWidget().parentWidget().daq.put("WC 03 04")
                    self.parentWidget().parentWidget().parentWidget().daq.put("WC 02 0A")

                    # this should set the veto to none (because we have a software veto)
                    # and the coinincidence to single, so we take all pulses
                    self.parentWidget().parentWidget().parentWidget().daq.put("WC 00 0F")
                  
                    self.mu_file = open(self.parentWidget().parentWidget().parentWidget().decayfilename,'w')        
                    self.dec_mes_start = now
                    #self.decaywidget.findChild("activate_mudecay").setChecked(True)
                    self.active(True)
                    #FIXME: is this intentional?
                    self.parentWidget().parentWidget().ratewidget.on_start_clicked()
                    self.pulsefile = self.mainwindow.pulseextractor.pulse_file
                    if not self.pulsefile:
                        self.mainwindow.pulsefilename = \
                            os.path.join(DATA_PATH,"%s_%s_HOURS_%s%s" %(self.mainwindow.now.strftime('%Y-%m-%d_%H-%M-%S'),
                                                                       "P",
                                                                       self.mainwindow.opts.user[0],
                                                                       self.mainwindow.opts.user[1]) )
                        self.mainwindow.pulse_mes_start = self.mainwindow.now
                        self.mainwindow.pulseextractor.pulse_file = open(self.mainwindow.pulsefilename,'w')
                        self.logger.debug("Starting to write pulses to %s" %self.mainwindow.pulsefilename)
                        self.mainwindow.writepulses = True

                else:
                    self.activateMuondecay.setChecked(False)
                    self.findChild(QtGui.QLabel,QtCore.QString("activesince")).setText(tr("Dialog", "" ,None, QtGui.QApplication.UnicodeUTF8))
                    self.active(False)

        else:
            reset_time = "WC 03 " + self.previous_coinc_time_03
            self.parentWidget().parentWidget().parentWidget().daq.put(reset_time)
            reset_time = "WC 02 " + self.previous_coinc_time_02
            self.parentWidget().parentWidget().parentWidget().daq.put(reset_time)
            self.logger.info('Muondecay mode now deactivated, returning to previous setting (if available)')
            self.parentWidget().parentWidget().parentWidget().statusbar.removeWidget(self.mu_label)
            #self.parentWidget().parentWidget().parentWidget().mudecaymode = False
            mtime = now - self.dec_mes_start
            mtime = round(mtime.seconds/(3600.),2) + mtime.days *86400
            self.logger.info("The muon decay measurement was active for %f hours" % mtime)
            newmufilename = self.parentWidget().parentWidget().parentWidget().decayfilename.replace("HOURS",str(mtime))
            shutil.move(self.parentWidget().parentWidget().parentWidget().decayfilename,newmufilename)
            #self.parentWidget().parentWidget().parentWidget().daq.put("CD")
            self.active(False)
            self.activateMuondecay.setChecked(False)
            self.findChild(QtGui.QLabel,QtCore.QString("activesince")).setText(tr("Dialog", "" ,None, QtGui.QApplication.UnicodeUTF8))
            self.parentWidget().parentWidget().ratewidget.on_stop_clicked()


class DAQWidget(BaseWidget):
    """
    Shows the DAQ message log. The message log can be written to a file.
    This widget has a command line to issue DAQ commands, as well as
    periodic commands within a user defined interval.

    :param logger: logger object
    :type logger: logging.Logger
    :param parent: parent widget
    """

    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)

        # raw output file
        self.output_file = None
        self.write_raw_file = False
        self.write_status = None

        # periodic call
        self.interval = 1
        self.command = None
        self.periodic_commands = []
        self.periodic_status = None
        self.periodic_call_timer = QtCore.QTimer()

        # daq msg log
        self.daq_msg_log = QtGui.QPlainTextEdit()
        self.daq_msg_log.setReadOnly(True)
        # 500 lines history
        self.daq_msg_log.document().setMaximumBlockCount(500)

        # input field and buttons
        self.label = QtGui.QLabel("Command")
        self.hello_edit = LineEdit()
        self.file_button = QtGui.QPushButton("Save RAW-File")
        self.periodic_button = QtGui.QPushButton("Periodic Call")

        # connect signals
        QtCore.QObject.connect(self.periodic_call_timer,
                               QtCore.SIGNAL("timeout()"),
                               self._execute_commands)
        QtCore.QObject.connect(self.hello_edit,
                               QtCore.SIGNAL("returnPressed()"),
                               self.on_hello_clicked)
        QtCore.QObject.connect(self.file_button,
                               QtCore.SIGNAL("clicked()"),
                               self.on_file_clicked)
        QtCore.QObject.connect(self.periodic_button,
                               QtCore.SIGNAL("clicked()"),
                               self.on_periodic_clicked)

        # add widgets to layout
        layout = QtGui.QGridLayout(self)
        layout.addWidget(self.daq_msg_log, 0, 0, 1, 4)
        layout.addWidget(self.label, 1, 0)
        layout.addWidget(self.hello_edit, 1, 1)
        layout.addWidget(self.file_button, 1, 2)
        layout.addWidget(self.periodic_button, 1, 3)

        self.setLayout(layout)

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
        if self.write_raw_file:
            self.write_raw_file = False
            self.file_button.setText("Save RAW-File")
            try:
                self.output_file.close()
            except IOError as e:
                self.logger.error("unable to close file '%s': %s" %
                                  (self.parent.rawfilename, str(e)))
            self.parent.statusbar.removeWidget(self.write_status)
        else:
            try:
                self.write_raw_file = True
                self.file_button.setText("Stop saving RAW-File")
                self.parent.daq.put("CE")

                # FIXME: rawfilename and raw_mes_start belong to this widget
                self.output_file = open(self.parent.rawfilename, "w")
                self.parent.raw_mes_start = datetime.datetime.now()

                self.write_status = QtGui.QLabel("Writing to %s" %
                                                 self.parent.rawfilename)
                self.parent.statusbar.addPermanentWidget(self.write_status)
            except IOError as e:
                self.logger.error("unable to open file '%s': %s" %
                                  (self.parent.rawfilename, str(e)))

    def on_periodic_clicked(self):
        """
        Issue a DAQ command periodically

        :returns: None
        """
        dialog = PeriodicCallDialog(self.command, self.interval)

        if dialog.exec_() == 1:
            self.interval = dialog.get_widget_value("interval")
            self.command = str(dialog.get_widget_value("command")).strip()

            # ignore empty commands
            if self.command == "":
                return

            self.periodic_commands = self.command.split('+')

            # stop timer and clear status if already running
            if self.periodic_call_timer.isActive():
                self.periodic_call_timer.stop()
                self.parent.statusbar.removeWidget(self.periodic_status)

            self.periodic_call_timer.start(self.interval * 1000)
            self.periodic_status = QtGui.QLabel(
                    '%s every %s sec' % (self.command, self.interval))
            self.parent.statusbar.addPermanentWidget(
                    self.periodic_status)

            # execute commands now
            self._execute_commands()
        else:
            try:
                self.periodic_call_timer.stop()
                self.parent.statusbar.removeWidget(self.periodic_status)
            except AttributeError:
                pass

    def _execute_commands(self):
        """
        Execute periodic commands

        :returns: None
        """
        for command in self.periodic_commands:
            self.daq_put(command)

    def update(self):
        """
        Update daq msg log

        :returns: None
        """
        msg = self.daq_get_last()
        self.daq_msg_log.appendPlainText(msg)

        if self.write_raw_file:
            self._write_to_file(msg)

    def _write_to_file(self, msg):
        """
        Write the "RAW" file

        :param msg: daq message
        :type msg: str
        :returns: None
        """

        # FIXME: 'nostatus' is a setting: uses 'get_setting()' for this
        if self.parent.nostatus:
            fields = msg.rstrip("\n").split(" ")
            if (len(fields) == 16) and (len(fields[0]) == 8):
                self.output_file.write(str(msg) + "\n")
            else:
                self.logger.debug(("Not writing line '%s' to file " +
                                  "because it does not contain " +
                                  "trigger data") % msg)
        else:
            self.output_file.write(str(msg) + "\n")

    def finish(self):
        """
        Cleanup

        :returns: None
        """
        if self.write_raw_file:
            self.output_file.close()
            # TODO: handle renaming of output file here


class GPSWidget(BaseWidget):

    def __init__(self, logger, parent=None):
        BaseWidget.__init__(self, logger, parent)
        self.mainwindow = self.parentWidget()
        self.logger = logger
        self.gps_dump = []
        self.read_lines = 13

        self.label           = QtGui.QLabel(tr('MainWindow','GPS Display:'))
        self.refresh_button  = QtGui.QPushButton(tr('MainWindow','Show GPS'))
        self.save_button     = QtGui.QPushButton(tr('MainWindow', 'Save to File'))

        QtCore.QObject.connect(self.refresh_button,
                              QtCore.SIGNAL("clicked()"),
                              self.on_refresh_clicked
                              )
        QtCore.QObject.connect(self.save_button,
                                QtCore.SIGNAL("clicked()"),
                                self.on_save_clicked
                                )
        self.text_box = QtGui.QPlainTextEdit()
        self.text_box.setReadOnly(True)
        # only 500 lines history
        self.text_box.document().setMaximumBlockCount(500)
        self.status_label = QtGui.QLabel(tr('MainWindow','Status: '))
        self.time_label = QtGui.QLabel(tr('MainWindow','GPS time: '))
        self.satellites_label = QtGui.QLabel(tr('MainWindow','#Satellites: '))
        self.chksum_label = QtGui.QLabel(tr('MainWindow','Checksum: '))
        self.latitude_label = QtGui.QLabel(tr('MainWindow','Latitude: '))
        self.longitude_label = QtGui.QLabel(tr('MainWindow','Longitude: '))
        self.altitude_label = QtGui.QLabel(tr('MainWindow','Altitude: '))
        self.posfix_label = QtGui.QLabel(tr('MainWindow','PosFix: '))
        self.status_box = QtGui.QLabel(tr('MainWindow',' Not read out'))
        self.time_box = QtGui.QLabel(tr('MainWindow','--'))
        self.satellites_box = QtGui.QLabel(tr('MainWindow','--'))
        self.chksum_box = QtGui.QLabel(tr('MainWindow','--'))
        self.latitude_box = QtGui.QLabel(tr('MainWindow','--'))
        self.longitude_box = QtGui.QLabel(tr('MainWindow','--'))
        self.altitude_box = QtGui.QLabel(tr('MainWindow','--'))
        self.posfix_box = QtGui.QLabel(tr('MainWindow','--'))

        gps_layout = QtGui.QGridLayout(self)
        gps_layout.addWidget(self.label,0,0,1,4)
        gps_layout.addWidget(self.status_label,1,0)
        gps_layout.addWidget(self.time_label,2,0)
        gps_layout.addWidget(self.satellites_label,3,0)
        gps_layout.addWidget(self.chksum_label,4,0)
        gps_layout.addWidget(self.latitude_label,1,2)
        gps_layout.addWidget(self.longitude_label,2,2)
        gps_layout.addWidget(self.altitude_label,3,2)
        gps_layout.addWidget(self.posfix_label,4,2)
        gps_layout.addWidget(self.status_box,1,1)
        gps_layout.addWidget(self.time_box,2,1)
        gps_layout.addWidget(self.satellites_box,3,1)
        gps_layout.addWidget(self.chksum_box,4,1)
        gps_layout.addWidget(self.latitude_box,1,3)
        gps_layout.addWidget(self.longitude_box,2,3)
        gps_layout.addWidget(self.altitude_box,3,3)
        gps_layout.addWidget(self.posfix_box,4,3)
        gps_layout.addWidget(self.text_box,6,0,1,4)
        gps_layout.addWidget(self.refresh_button,7,0,1,4) 
        #gps_layout.addWidget(self.save_button,1,2) 

        if self.active():
            self.logger.info("Activated GPS display.")
            self.on_refresh_clicked()

    def on_refresh_clicked(self):
        """
        Display/refresh the GPS information
        """
        self.refresh_button.setEnabled(False)
        self.gps_dump = [] 
        self.logger.info('Reading GPS.')
        self.mainwindow.process_incoming()
        self.switch_active(True)        
        self.mainwindow.daq.put('DG')
        self.mainwindow.process_incoming()
        #for count in range(self.read_lines):
        #    msg = self.mainwindow.inqueue.get(True)
        #    self.gps_dump.append(msg)
        #self.calculate()
        #self.logger.info('GPS readout done.')

    def on_save_clicked(self):
        """
        Save the GPS data to an extra file
        """
        #self.outputfile = open(self.mainwindow.rawfilename,"w")
        #self.file_label = QtGui.QLabel(tr('MainWindow','Writing to %s'%self.mainwindow.rawfilename))
        #self.write_file = True
        #self.mainwindow.raw_mes_start = datetime.datetime.now()
        #self.mainwindow.statusbar.addPermanentWidget(self.file_label)
        self.text_box.appendPlainText('save to clicked - function out of order')        
        self.logger.info("Saving GPS informations still disabled.")


    def switch_active(self, switch = False):
        """
        Switch the GPS activation status.
        """
        if switch is None:
            if self.active():
                self.active(False)
            else:
                self.active(True)
        else:
            self.active(switch)
        return self.active()
    
    def calculate(self):
        """
        Readout the GPS information and display it in the tab.
        """
        if len(self.gps_dump) < self.read_lines:
            self.logger.warning('Error retrieving GPS information.')
            return False
        __satellites = 0
        __status = False
        __gps_time = ''
        __latitude = ''
        __longitude = ''
        __altitude = ''
        __posfix = 0
        __chksum = False
        self.refresh_button.setEnabled(True)
        try:

            if str(self.gps_dump[3]).strip().replace('Status:','').strip() == 'A (valid)':
                self.logger.info('Valid GPS signal: found %i ' %(__satellites))
                __status = True
                __satellites = int(str(self.gps_dump[8]).strip().replace('Sats used:', '').strip())
                __posfix = int(str(self.gps_dump[4]).strip().replace('PosFix#:', '').strip())
                __gps_time = str(self.gps_dump[2]).strip().replace('Date+Time:', '').strip()
                if str(self.gps_dump[12]).strip().replace('ChkSumErr:', '').strip() == '0':
                    __chksum = True
                else:
                    __chksum = False
 
                __altitude = str(self.gps_dump[7]).strip().replace('Altitude:', '').strip()

                __latitude = str(self.gps_dump[5]).strip().replace('Latitude:', '').strip()

                __longitude = str(self.gps_dump[6]).strip().replace('Longitude:', '').strip()

            else:
                __status = False
                self.logger.info('Invalid GPS signal.')

            self.gps_dump = []
        except:
            self.logger.warning('Error evaluating GPS information.')
            self.gps_dump = []
            self.switch_active(False)
            return False

        if __status:
            __status = 'Valid'
        else:
            __status = 'Invalid'
        if __chksum:
            __chksum = 'No Error'
        else:
            __chksum = 'Error'
                    
        self.status_box.setText(str(__status))
        self.time_box.setText(str(__gps_time))
        self.satellites_box.setText(str(__satellites))
        self.chksum_box.setText(str(__chksum))
        self.latitude_box.setText(str(__latitude))
        self.longitude_box.setText(str(__longitude))
        self.altitude_box.setText(str(__altitude))
        self.posfix_box.setText(str(__posfix))

        self.text_box.appendPlainText('********************')
        self.text_box.appendPlainText('STATUS     : %s' %(str(__status)))
        self.text_box.appendPlainText('TIME          : %s' %(str(__gps_time)))
        self.text_box.appendPlainText('Altitude     : %s' %(str(__altitude)))
        self.text_box.appendPlainText('Latitude     : %s' %(str(__latitude)))
        self.text_box.appendPlainText('Longitude  : %s' %(str(__longitude)))
        self.text_box.appendPlainText('Satellites    : %s' %(str(__satellites)))
        self.text_box.appendPlainText('Checksum   : %s' %(str(__chksum)))
        self.text_box.appendPlainText('********************')

        self.switch_active(False)
        return True
