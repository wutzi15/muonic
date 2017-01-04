# -*- coding: utf-8 -*-
"""
Provides the main window for the gui part of muonic
"""
from os import path
import datetime
import time
import webbrowser

from PyQt4 import QtGui
from PyQt4 import QtCore

from muonic import __version__, __source_location__
from muonic import __docs_hosted_at__, __manual_hosted_at__
from muonic.analysis import PulseExtractor
from muonic.daq import DAQIOError
from muonic.gui.helpers import set_large_plot_style
from muonic.gui.dialogs import ThresholdDialog, ConfigDialog
from muonic.gui.dialogs import HelpDialog, AdvancedDialog
from muonic.gui.widgets import VelocityWidget, PulseAnalyzerWidget
from muonic.gui.widgets import DecayWidget, DAQWidget, RateWidget
from muonic.gui.widgets import GPSWidget, StatusWidget
from muonic.util import update_setting, get_setting
from muonic.util import apply_default_settings, get_muonic_filename
from muonic.util import get_data_directory


class Application(QtGui.QMainWindow):
    """
    The main application

    :param daq: daq card connection
    :type daq: muonic.daq.provider.BaseDAQProvider
    :param logger: logger object
    :type logger: logging.Logger
    :param opts: command line options
    :type opts: Namespace
    """
    def __init__(self, daq, logger, opts):
        QtGui.QMainWindow.__init__(self)

        # start time of the application
        self.start_time = datetime.datetime.utcnow()

        # apply default settings first
        apply_default_settings()

        QtCore.QLocale.setDefault(QtCore.QLocale("en_us"))
        self.setWindowTitle("muonic")
        self.setWindowIcon(QtGui.QIcon(path.join(path.dirname(__file__),
                                                   "muonic.xpm")))

        # params
        self.daq = daq
        self.logger = logger
        self.opts = opts

        # tab widget to hold the different physics widgets
        self.tab_widget = QtGui.QTabWidget(self)

        # widget store for the tab widgets to reference later
        self._widgets = dict()

        # setup status bar
        self.status_bar = QtGui.QMainWindow.statusBar(self)

        # last daq message
        self.last_daq_msg = False

        # detected pulses
        self.pulses = None

        # generate filenames
        self.rate_filename = get_muonic_filename(self.start_time,
                                                 "R", opts.user)
        self.raw_filename = get_muonic_filename(self.start_time,
                                                "DAQ", opts.user)
        self.decay_filename = get_muonic_filename(self.start_time,
                                                  "D", opts.user)
        self.velocity_filename = get_muonic_filename(self.start_time,
                                                     "V", opts.user)
        self.pulse_filename = get_muonic_filename(self.start_time,
                                                  "P", opts.user)

        # store command line settings
        update_setting("write_pulses", opts.write_pulses)
        update_setting("write_daq_status", opts.write_daq_status)
        update_setting("time_window", opts.time_window)

        # we have to ensure that the DAQ card does not sent any automatic
        # status reports every x seconds if 'write_daq_status' is set to False
        if not opts.write_daq_status:
            # disable status reporting
            self.daq.put('ST 0')

        # get the last configuration from the card
        self.get_configuration_from_daq_card()

        # create pulse extractor for direct analysis
        self.pulse_extractor = PulseExtractor(logger, self.pulse_filename)

        if opts.write_pulses:
            # write pulses to file all the time
            self.daq.put('CE')
            self.pulse_extractor.write_pulses(True)

        # create tabbed widgets
        self.setup_tab_widgets()

        self.setCentralWidget(self.tab_widget)

        # widgets which should be calculated in process_incoming.
        # The widget is only calculated when it is set to active (True)
        # via widget.active(True). only widgets which need pulses go here
        self.pulse_widgets = [self.get_widget("pulse"),
                              self.get_widget("decay"),
                              self.get_widget("velocity")]

        # widgets which should be dynamically updated by the timer
        # should be in this list
        self.dynamic_widgets = [self.get_widget("rate"),
                                self.get_widget("pulse"),
                                self.get_widget("decay"),
                                self.get_widget("velocity")]

        # timer to periodically call processIncoming and check
        # what is in the queue
        self.timer = QtCore.QTimer()
        QtCore.QObject.connect(self.timer,
                               QtCore.SIGNAL("timeout()"),
                               self.process_incoming)

        # time update widgets the have dynamic plots in them
        self.widget_updater = QtCore.QTimer()
        QtCore.QObject.connect(self.widget_updater,
                               QtCore.SIGNAL("timeout()"),
                               self.update_dynamic)

        self.logger.info("Time window is %4.2f" % opts.time_window)

        self.setup_plot_style()
        self.setup_menus()
        self.process_incoming()

        # start update timers
        self.timer.start(1000)
        self.widget_updater.start(opts.time_window * 1000)

    def get_configuration_from_daq_card(self):
        """
        Get the initial threshold and channel configuration
        from the DAQ card.

        :returns: None
        """
        # get the thresholds
        self.daq.put('TL')
        # give the daq some time to react
        time.sleep(0.5)

        while self.daq.data_available():
            try:
                msg = self.daq.get(0)
                self.get_thresholds_from_msg(msg)

            except DAQIOError:
                self.logger.debug("Queue empty!")

        # get the channel config
        self.daq.put('DC')
        # give the daq some time to react
        time.sleep(0.5)

        while self.daq.data_available():
            try:
                msg = self.daq.get(0)
                self.get_channels_from_msg(msg)

            except DAQIOError:
                self.logger.debug("Queue empty!")

    def setup_tab_widgets(self):
        """
        Creates the widgets and adds tabs

        :returns: None
        """
        self.add_widget("rate", "Muon Rates",
                        RateWidget(self.logger, self.rate_filename,
                                   parent=self))
        self.add_widget("pulse", "Pulse Analyzer",
                        PulseAnalyzerWidget(self.logger, self.pulse_extractor,
                                            parent=self))
        self.add_widget("decay", "Muon Decay",
                        DecayWidget(self.logger, self.decay_filename,
                                    self.pulse_extractor, parent=self))
        self.add_widget("velocity", "Muon Velocity",
                        VelocityWidget(self.logger, self.velocity_filename,
                                       self.pulse_extractor, parent=self))
        self.add_widget("status", "Status",
                        StatusWidget(self.logger, parent=self))
        self.add_widget("daq", "DAQ Output",
                        DAQWidget(self.logger, self.raw_filename, parent=self))
        self.add_widget("gps", "GPS Output",
                        GPSWidget(self.logger, parent=self))

    def setup_plot_style(self):
        """
        Setup the plot style depending on screen size.

        :returns: None
        """
        desktop = QtGui.QDesktopWidget()
        screen_size = QtCore.QRectF(desktop.screenGeometry(
                desktop.primaryScreen()))
        screen_x = screen_size.x() + screen_size.width()
        screen_y = screen_size.y() + screen_size.height()

        self.logger.info("Screen with size %i x %i detected!" %
                         (screen_x, screen_y))

        # Screens lager than 1600*1200 use large plot style.
        if screen_x * screen_y >= 1920000:
            set_large_plot_style()

    def setup_menus(self):
        """
        Setup the menu bar and populate menus.

        :returns: None
        """
        # create the menubar
        menu_bar = self.menuBar()

        # create file menu
        file_menu = menu_bar.addMenu('&File')

        muonic_data_action = QtGui.QAction('Open Data Folder', self)
        muonic_data_action.setStatusTip('Open the folder with the data files written by muonic.')
        muonic_data_action.setShortcut('Ctrl+O')
        self.connect(muonic_data_action, QtCore.SIGNAL('triggered()'),
                     self.open_muonic_data)

        file_menu.addAction(muonic_data_action)

        exit_action = QtGui.QAction(QtGui.QIcon(
                "/usr/share/icons/gnome/24x24/actions/exit.png"), 'Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        self.connect(exit_action, QtCore.SIGNAL('triggered()'),
                     QtCore.SLOT('close()'))

        file_menu.addAction(exit_action)

        # create settings menu
        settings_menu = menu_bar.addMenu('&Settings')

        config_action = QtGui.QAction('Channel Configuration', self)
        config_action.setStatusTip('Configure the Coincidences and channels')
        self.connect(config_action, QtCore.SIGNAL('triggered()'),
                     self.config_menu)

        thresholds_action = QtGui.QAction('Thresholds', self)
        thresholds_action.setStatusTip('Set trigger thresholds')
        self.connect(thresholds_action, QtCore.SIGNAL('triggered()'),
                     self.threshold_menu)

        advanced_action = QtGui.QAction('Advanced Configurations', self)
        advanced_action.setStatusTip('Advanced configurations')
        self.connect(advanced_action, QtCore.SIGNAL('triggered()'),
                     self.advanced_menu)

        settings_menu.addAction(config_action)
        settings_menu.addAction(thresholds_action)
        settings_menu.addAction(advanced_action)

        # create help menu
        help_menu = menu_bar.addMenu('&Help')

        manualdoc_action = QtGui.QAction('Website with Manual', self)
        self.connect(manualdoc_action, QtCore.SIGNAL('triggered()'),
                     self.manualdoc_menu)

        sphinxdoc_action = QtGui.QAction('Technical documentation', self)
        self.connect(sphinxdoc_action, QtCore.SIGNAL('triggered()'),
                     self.sphinxdoc_menu)

        commands_action = QtGui.QAction('DAQ Commands', self)
        commands_action.setShortcut('F1')
        self.connect(commands_action, QtCore.SIGNAL('triggered()'),
                     self.help_menu)

        about_action = QtGui.QAction('About muonic', self)
        self.connect(about_action, QtCore.SIGNAL('triggered()'),
                     self.about_menu)

        help_menu.addAction(manualdoc_action)
        help_menu.addAction(commands_action)
        help_menu.addAction(sphinxdoc_action)
        help_menu.addAction(about_action)

    def add_widget(self, name, label, widget):
        """
        Adds widget to the store.

        Raises WidgetWithNameExistsError if a widget of that name already
        exists and TypeError if widget is no subclass of QtGui.QWidget.

        :param name: widget name
        :type name: str
        :param label: the tab label
        :type label: str
        :param widget: widget object
        :type widget: object
        :returns: None
        :raises: WidgetWithNameExistsError, TypeError
        """

        if widget is None:
            return
        if self.have_widget(name):
            raise WidgetWithNameExistsError(
                    "widget with name '%s' already exists" % name)
        else:
            if not isinstance(widget, QtGui.QWidget):
                raise TypeError("widget has to be a subclass 'QtGui.QWidget'")
            else:
                self.tab_widget.addTab(widget, label)
                self._widgets[name] = widget

    def have_widget(self, name):
        """
        Returns true if widget with name exists, False otherwise.

        :param name: widget name
        :type name: str
        :returns: bool
        """
        return name in self._widgets

    def get_widget(self, name):
        """
        Retrieved a widget from the store.

        :param name: widget name
        :type name: str
        :returns: object
        """
        return self._widgets.get(name)

    def is_widget_active(self, name):
        """
        Returns True if the widget exists and is active, False otherwise

        :param name: widget name
        :type name: str
        :returns: bool
        """
        if self.have_widget(name):
            return self.get_widget(name).active()
        return False

    def threshold_menu(self):
        """
        Shows thresholds dialog.

        :returns: None
        """
        # get the actual thresholds from the DAQ card
        self.daq.put('TL')

        # wait explicitly until the thresholds get loaded
        self.logger.info("loading threshold information..")
        time.sleep(1.5)

        # get thresholds from settings
        thresholds = [get_setting("threshold_ch%d" % i, 300) for i in range(4)]

        # show dialog
        dialog = ThresholdDialog(thresholds)

        if dialog.exec_() == 1:
            commands = []

            # update thresholds config
            for ch in range(4):
                val = dialog.get_widget_value("threshold_ch_%d" % ch)
                update_setting("threshold_ch%d" % ch, val)
                commands.append("TL %d %s" % (ch, val))

            # apply new thresholds to daq card
            for cmd in commands:
                self.daq.put(cmd)
                self.logger.info("Set threshold of channel %s to %s" %
                                 (cmd.split()[1], cmd.split()[2]))

        self.daq.put('TL')
  
    def open_muonic_data(self):
        """
        Opens the folder with the data files. Usually in $HOME/muonic_data
        """

        import webbrowser
        webbrowser.open("file://" + get_data_directory())

    def config_menu(self):
        """
        Show the channel config dialog.

        :returns: None
        """
        # get the actual channels from the DAQ card
        self.daq.put("DC")

        # wait explicitly until the channels get loaded
        self.logger.info("loading channel information...")
        time.sleep(1)

        # get current config values
        channel_config = [get_setting("active_ch%d" % i) for i in range(4)]
        coincidence_config = [get_setting("coincidence%d" % i)
                              for i in range(4)]
        veto = get_setting("veto")
        veto_config = [get_setting("veto_ch%d" % i) for i in range(3)]

        # show dialog
        dialog = ConfigDialog(channel_config, coincidence_config,
                              veto, veto_config)

        if dialog.exec_() == 1:

            # get and update channel and coincidence config
            for i in range(4):
                channel_config[i] = dialog.get_widget_value(
                        "channel_checkbox_%d" % i)
                coincidence_config[i] = dialog.get_widget_value(
                        "coincidence_checkbox_%d" % i)

                update_setting("active_ch%d" % i, channel_config[i])
                update_setting("coincidence%d" % i, coincidence_config[i])

            # get and update veto state
            veto = dialog.get_widget_value("veto_checkbox")
            update_setting("veto", veto)

            # get and update veto channel config
            for i in range(3):
                veto_config[i] = dialog.get_widget_value(
                        "veto_checkbox_%d" % i)

                update_setting("veto_ch%d" % i, veto_config[i])

            # build daq message to apply the new config to the card
            tmp_msg = ""

            if veto:
                if veto_config[0]:
                    tmp_msg += "01"
                elif veto_config[1]:
                    tmp_msg += "10"
                elif veto_config[2]:
                    tmp_msg += "11"
                else:
                    tmp_msg += "00"
            else:
                tmp_msg += "00"

            coincidence_set = False

            # singles, twofold, threefold, fourfold
            for i, coincidence in enumerate(["00", "01", "10", "11"]):
                if coincidence_config[i]:
                    tmp_msg += coincidence
                    coincidence_set = True

            if not coincidence_set:
                tmp_msg += "00"
    
            # now calculate the correct expression for the first
            # four bits
            self.logger.debug("The first four bits are set to %s" % tmp_msg)
            msg = "WC 00 %s" % hex(int(''.join(tmp_msg), 2))[-1].capitalize()
    
            channel_set = False
            enable = ['0', '0', '0', '0']

            for i, active in enumerate(reversed(channel_config)):
                if active:
                    enable[i] = '1'
                    channel_set = True
            
            if channel_set:
                msg += hex(int(''.join(enable), 2))[-1].capitalize()
            else:
                msg += '0'

            # send the message to the daq card
            self.daq.put(msg)

            self.logger.info("The following message was sent to DAQ: %s" % msg)

            for i in range(4):
                self.logger.debug("channel%d selected %s" %
                                  (i, channel_config[i]))

            for i, name in enumerate(["singles", "twofold",
                                      "threefold", "fourfold"]):
                self.logger.debug("coincidence %s %s" %
                                  (name, coincidence_config[i]))

        self.daq.put("DC")
           
    def advanced_menu(self):
        """
        Show a config dialog for advanced options, ie. gate width,
        interval for the rate measurement, options for writing pulse file
        and the write_daq_status option.

        :returns: None
        """
        # get the actual channels from the DAQ card
        self.daq.put("DC")

        # wait explicitly until the channels get loaded
        self.logger.info("loading channel information...")
        time.sleep(1)

        # show dialog
        dialog = AdvancedDialog(get_setting("gate_width"),
                                get_setting("time_window"),
                                get_setting("write_daq_status"))

        if dialog.exec_() == 1:
            # update time window
            time_window = float(dialog.get_widget_value("time_window"))

            if time_window < 0.01 or time_window > 10000.:
                self.logger.warning("Time window too small or too big, " +
                                    "resetting to 5 s.")
                time_window = 5.0

            update_setting("time_window", time_window)

            # update write_daq_status
            write_daq_status = dialog.get_widget_value("write_daq_status")
            update_setting("write_daq_status", write_daq_status)

            # update gate width
            gate_width = int(dialog.get_widget_value("gate_width"))
            update_setting("gate_width", gate_width)

            # transform gate width for daq msg
            gate_width = bin(gate_width // 10).replace('0b', '').zfill(16)
            gate_width_03 = format(int(gate_width[0:8], 2), 'x').zfill(2)
            gate_width_02 = format(int(gate_width[8:16], 2), 'x').zfill(2)

            # set gate widths
            self.daq.put("WC 03 %s" % gate_width_03)
            self.daq.put("WC 02 %s" % gate_width_02)

            # adjust the update interval
            self.widget_updater.start(time_window * 1000)

            self.logger.debug("Writing gate width WC 02 %s WC 03 %s" %
                              (gate_width_02, gate_width_03))
            self.logger.debug("Setting time window to %.2f " % time_window)
            self.logger.debug("Switching write_daq_status option to %s" %
                              write_daq_status)

        self.daq.put("DC")

    def help_menu(self):
        """
        Show a simple help dialog.

        :returns: None
        """
        HelpDialog().exec_()
        
    def about_menu(self):
        """
        Show a link to the online documentation.

        :returns: None
        """
        QtGui.QMessageBox.information(self, "about muonic",
                                      "version: %s\n source located at: %s" %
                                      (__version__, __source_location__))

    def sphinxdoc_menu(self):
        """
        Show the sphinx documentation that comes with muonic in a
        browser.

        :returns: None
        """
        docs = __docs_hosted_at__

        self.logger.debug("Opening docs from %s" % docs)

        if not webbrowser.open(docs):
            self.logger.warning("Can not open webbrowser! " +
                                "Browse to %s to see the docs" % docs)

    def manualdoc_menu(self):
        """
        Show the manual that comes with muonic in a pdf viewer.

        :returns: None
        """
        docs = __manual_hosted_at__

        self.logger.info("Opening docs from %s" % docs)

        if not webbrowser.open(docs):
            self.logger.warning("Can not open PDF reader!")

    def get_thresholds_from_msg(self, msg):
        """
        Explicitly scan message for threshold information.

        Return True if found, False otherwise.

        :param msg: daq message
        :type msg: str
        :returns: bool
        """
        if msg.startswith('TL') and len(msg) > 9:
            msg = msg.split('=')
            update_setting("threshold_ch0", int(msg[1][:-2]))
            update_setting("threshold_ch1", int(msg[2][:-2]))
            update_setting("threshold_ch2", int(msg[3][:-2]))
            update_setting("threshold_ch3", int(msg[4]))
            self.logger.debug("Got Thresholds %d %d %d %d" %
                              tuple([get_setting("threshold_ch%d" % i)
                                     for i in range(4)]))
            return True
        else:
            return False
        
    def get_channels_from_msg(self, msg):
        """
        Explicitly scan message for channel information.

        Return True if found, False otherwise.

        DC gives:

        DC C0=23 C1=71 C2=0A C3=00
        
        Which has the meaning:

        MM - 00 -> 8bits for channel enable/disable, coincidence and veto

        +---------------------------------------------------------------------+
        |                              bits                                   |
        +====+====+===========+===========+========+========+========+========+
        |7   |6   |5          |4          |3       |2       |1       |0       |
        +----+----+-----------+-----------+--------+--------+--------+--------+
        |veto|veto|coincidence|coincidence|channel3|channel2|channel1|channel0|
        +----+----+-----------+-----------+--------+--------+--------+--------+

        +-----------------+
        |Set bits for veto|
        +=================+
        |00 - ch0 is veto |
        +-----------------+
        |01 - ch1 is veto |
        +-----------------+
        |10 - ch2 is veto |
        +-----------------+
        |11 - ch3 is veto |
        +-----------------+

        +------------------------+
        |Set bits for coincidence|
        +========================+
        |00 - singles            |
        +------------------------+
        |01 - twofold            |
        +------------------------+
        |10 - threefold          |
        +------------------------+
        |11 - fourfold           |
        +------------------------+

        :param msg: daq message
        :type msg: str
        :returns: bool
        """
        if msg.startswith('DC ') and len(msg) > 25:
            msg = msg.split(' ')

            coincidence_time = msg[4].split('=')[1] + msg[3].split('=')[1]
            msg = bin(int(msg[1][3:], 16))[2:].zfill(8)
            veto_config = msg[0:2]
            coincidence_config = msg[2:4]
            channel_config = msg[4:8]

            update_setting("gate_width", int(coincidence_time, 16) * 10)

            # set default veto config
            for i in range(4):
                if i == 0:
                    update_setting("veto", True)
                else:
                    update_setting("veto_ch%d" % (i - 1), False)

            # update channel config
            for i in range(4):
                update_setting("active_ch%d" % i,
                               channel_config[3 - i] == '1')

            # update coincidence config
            for i, seq in enumerate(['00', '01', '10', '11']):
                update_setting("coincidence%d" % i,
                               coincidence_config == seq)

            # update veto config
            for i, seq in enumerate(['00', '01', '10', '11']):
                if veto_config == seq:
                    if i == 0:
                        update_setting("veto", False)
                    else:
                        update_setting("veto_ch%d" % (i - 1), True)

            self.logger.debug('gate width timew indow %d ns' %
                              get_setting("gate_width"))
            self.logger.debug("Got channel configurations: %d %d %d %d" %
                              tuple([get_setting("active_ch%d" % i)
                                     for i in range(4)]))
            self.logger.debug("Got coincidence configurations: %d %d %d %d" %
                              tuple([get_setting("coincidence%d" % i)
                                     for i in range(4)]))
            self.logger.debug("Got veto configurations: %d %d %d %d" %
                              tuple([get_setting("veto")] +
                                    [get_setting("veto_ch%d" % i)
                                     for i in range(3)]))

            return True
        else:
            return False

    def process_incoming(self):
        """
        This functions gets everything out of the daq.

        Handles all the messages currently in the daq
        and passes the results to the corresponding widgets.

        :returns: None
        """
        while self.daq.data_available():
            try:
                msg = self.daq.get(0)
            except DAQIOError:
                self.logger.debug("Queue empty!")
                return None

            # make daq msg public for child widgets
            self.last_daq_msg = msg

            # Check contents of message and do what it says
            self.get_widget("daq").update()
            
            gps_widget = self.get_widget("gps")

            # try to extract GPS information if widget is active and enabled
            if gps_widget.active() and gps_widget.isEnabled():
                gps_widget.update()
                continue
                
            status_widget = self.get_widget("status")

            # update status widget if active
            if status_widget.isVisible() and status_widget.active():
                status_widget.update()

            decay_widget = self.get_widget("decay")

            # update previous coincidence config on decay widget if active
            if msg.startswith('DC') and len(msg) > 2 and decay_widget.active():
                try:
                    split_msg = msg.split(" ")
                    t_03 = split_msg[4].split("=")[1]
                    t_02 = split_msg[3].split("=")[1]
                    decay_widget.set_previous_coincidence_times(t_03, t_02)
                except Exception:
                    self.logger.debug('Wrong DC command.')
                continue

            # check for threshold information
            if self.get_thresholds_from_msg(msg):
                continue

            # check for channel configuration
            if self.get_channels_from_msg(msg):
                continue

            # ignore status messages
            if msg.startswith('ST') or len(msg) < 50:
                continue

            # calculate rate
            if self.get_widget("rate").calculate():
                continue

            # extract pulses if needed
            if (get_setting("write_pulses") or
                    self.is_widget_active("pulse") or
                    self.is_widget_active("decay") or
                    self.is_widget_active("velocity")):
                self.pulses = self.pulse_extractor.extract(msg)

            # trigger calculation on all pulse widgets
            self.calculate_pulses()

    def calculate_pulses(self):
        """
        Runs the calculate function of pulse widgets if they are active
        and pulses are available.

        :returns: None
        """
        for widget in self.pulse_widgets:
            if widget.active() and (self.pulses is not None):
                widget.calculate(self.pulses)

    def update_dynamic(self):
        """
        Update dynamic widgets.

        :returns: None
        """
        for widget in self.dynamic_widgets:
            if widget.active():
                widget.update()

    def closeEvent(self, ev):
        """
        Is triggered when it is attempted to close the application.
        Will perform some cleanup before closing.

        :param ev: event
        :type ev: QtGui.QCloseEvent
        :returns: None
        """
        self.logger.info("Attempting to close application")

        # ask kindly if the user is really sure if she/he wants to exit
        reply = QtGui.QMessageBox.question(self, "Attention!",
                                           "Do you really want to exit?",
                                           QtGui.QMessageBox.Yes |
                                           QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            self.timer.stop()
            self.widget_updater.stop()

            for key, widget in self._widgets.items():
                # run finish hook on each widget, e.g. close and
                # rename files if necessary
                widget.finish()

            # run finish hook on pulse extractor to close and
            # rename pulse file
            self.pulse_extractor.finish()

            time.sleep(0.5)

            self.emit(QtCore.SIGNAL('lastWindowClosed()'))
            ev.accept()
        else:
            # don't close the application
            ev.ignore()


class WidgetWithNameExistsError(Exception):
    """
    Exception that gets raised if it is attempted to overwrite a
    widget reference that already exists.
    """
    pass
