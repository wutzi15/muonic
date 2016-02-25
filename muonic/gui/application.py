"""
Provides the main window for the gui part of muonic
"""
import datetime
import os
import shutil
import time
import webbrowser

from PyQt4 import QtGui
from PyQt4 import QtCore

from muonic import __version__, __source_location__
from muonic import __docs_hosted_at__, __manual_hosted_at__
from muonic import DATA_PATH
from muonic.analysis.analyzer import PulseExtractor
from muonic.daq import DAQIOError
from muonic.gui.styles import LargeScreenMPStyle
from muonic.gui.dialogs import ThresholdDialog, ConfigDialog
from muonic.gui.dialogs import HelpDialog, AdvancedDialog
from muonic.gui.widgets import VelocityWidget, PulseAnalyzerWidget
from muonic.gui.widgets import DecayWidget, DAQWidget, RateWidget
from muonic.gui.widgets import GPSWidget, StatusWidget
from muonic.util import add_widget, get_widget, update_setting, get_setting


tr = QtCore.QCoreApplication.translate

# create data path if not present
if not os.path.isdir(DATA_PATH):
    os.mkdir(DATA_PATH, 0755)


class Application(QtGui.QMainWindow):
    """
    The main application
    """

    def __init__(self, daq, logger, opts,  win_parent=None):
        QtGui.QMainWindow.__init__(self, win_parent)
        self.daq = daq
        self.opts = opts
        # try to establish upstream compatibility
        # B. introduced a DAQMessage here, but I think
        # this is overkill
        # however, making it a member allows to distribute
        # it more easily to daughter widgets
        self.daq_msg = False

        # we have to ensure that the DAQcard does not sent
        # any automatic status reports every x seconds
        #FIXME: there was an option for that!
        self.nostatus = opts.nostatus
        if self.nostatus:
            self.daq.put('ST 0')

        QtCore.QLocale.setDefault(QtCore.QLocale("en_us"))
        self.setWindowTitle(QtCore.QString("muonic"))
        self.statusbar = QtGui.QMainWindow.statusBar(self)
        self.logger = logger

        self.setup_screen()

        # put the file in the data directory
        # we chose a global format for naming the files -> decided on 18/01/2012
        # we use GMT times
        # "Zur einheitlichen Datenbezeichnung schlage ich folgendes Format vor:
        # JJJJ-MM-TT_y_x_vn.dateiformat (JJJJ-Jahr; MM-Monat; TT-Speichertag bzw.
        # Beendigung der Messung; y: G oder L ausw?hlen, G steht f?r **We add R for rate P for pulses and RW for RAW **
        # Geschwindigkeitsmessung/L f?r Lebensdauermessung; x-Messzeit in Stunden;
        # v-erster Buchstabe Vorname; n-erster Buchstabe Familienname)."
        # TODO: consistancy....        
 
        # the time when the rate measurement is started
        self.now = datetime.datetime.now()

        # new start
        filename_template = "%s_%%s_HOURS_%s" % (self.now.strftime('%Y-%m-%d_%H-%M-%S'), opts.user[:2])
        self.logger.info("filename_template: " + filename_template)

        filename_r = os.path.join(DATA_PATH, filename_template % "R")

        self.logger.info("filename_r: " + filename_r)
        # new end

        self.filename = os.path.join(DATA_PATH, "%s_%s_HOURS_%s%s" % (self.now.strftime('%Y-%m-%d_%H-%M-%S'), "R", opts.user[0], opts.user[1]))
        self.logger.debug("Writing Rates to %s." %self.filename)
        self.rawfilename = os.path.join(DATA_PATH, "%s_%s_HOURS_%s%s" % (self.now.strftime('%Y-%m-%d_%H-%M-%S'), "RAW", opts.user[0], opts.user[1]))
        self.raw_mes_start = False

        self.decayfilename = os.path.join(DATA_PATH, "%s_%s_HOURS_%s%s" % (self.now.strftime('%Y-%m-%d_%H-%M-%S'), "L", opts.user[0], opts.user[1]))
        self.pulse_mes_start = None
        self.writepulses = opts.writepulses
        if opts.writepulses:
                self.daq.put('CE')
                self.pulsefilename = os.path.join(DATA_PATH, "%s_%s_HOURS_%s%s" % (self.now.strftime('%Y-%m-%d_%H-%M-%S'), "P", opts.user[0], opts.user[1]))
                self.logger.debug("Writing pulses to %s." %self.pulsefilename)
                self.pulse_mes_start = self.now
        else:
                self.pulsefilename = ''
                self.pulse_mes_start = False

        # update_setting("write_pulses", opts.writepulses)

        self.daq.put('TL')  # get the thresholds
        time.sleep(0.5)  # give the daq some time to ract
        self.threshold_ch0 = 300
        self.threshold_ch1 = 300
        self.threshold_ch2 = 300
        self.threshold_ch3 = 300

        self.channelcheckbox_0 = True
        self.channelcheckbox_1 = True
        self.channelcheckbox_2 = True
        self.channelcheckbox_3 = True
        self.coincidencecheckbox_0 = True
        self.coincidencecheckbox_1 = False
        self.coincidencecheckbox_2 = False
        self.coincidencecheckbox_3 = False
        self.vetocheckbox = False
        self.vetocheckbox_0 = False
        self.vetocheckbox_1 = False
        self.vetocheckbox_2 = False

        # # channel configuration and thresholds
        # for i in range(4):
        #     update_setting("threshold_ch%d" % i, 300)
        #     update_setting("active_ch%d" % i, True)
        #     update_setting("coincidence%d" % i, True if i == 0 else False)
        #     if i == 0:
        #         update_setting("veto", False)
        #     else:
        #         update_setting("veto_ch%d" % i, False)

        # # advanced configuration
        # update_setting("write_daq_status", not opts.nostatus)
        # update_setting("time_window", opts.timewindow)
        # update_setting("coincidence_time", 0.)
        
        while self.daq.data_available():
            try:
                msg = self.daq.get(0)
                self.get_thresholds_from_queue(msg)

            except DAQIOError:
                self.logger.debug("Queue empty!")

        self.coincidence_time = 0.

        self.daq.put('DC')  # get the channel config
        time.sleep(0.5)  # give the daq some time to react
        while self.daq.data_available():
            try:
                msg = self.daq.get(0)
                self.get_channels_from_queue(msg)

            except DAQIOError:
                self.logger.debug("Queue empty!")
                
        # the pulseextractor for direct analysis
        self.pulseextractor = PulseExtractor(pulsefile=self.pulsefilename)
        self.pulses = None

        # A timer to periodically call processIncoming and check what is
        # in the queue
        
        # tab widget to hold the different physics widgets
        self.tab_widget = QtGui.QTabWidget(self)

        self.tab_widget.mainwindow = self.parentWidget()

        add_widget("main", self.parentWidget())

        self.tab_widget.addTab(RateWidget(logger, parent=self), "Muon Rates")
        self.tab_widget.ratewidget = self.tab_widget.widget(0)

        add_widget("rate", self.tab_widget.widget(0))

        self.tab_widget.addTab(PulseAnalyzerWidget(logger, parent=self), "Pulse Analyzer")
        self.tab_widget.pulseanalyzerwidget = self.tab_widget.widget(1)

        add_widget("pulse", self.tab_widget.widget(1))

        self.tab_widget.addTab(DecayWidget(logger, parent=self), "Muon Decay")
        self.tab_widget.decaywidget = self.tab_widget.widget(2)

        add_widget("decay", self.tab_widget.widget(2))
      
        self.tab_widget.addTab(VelocityWidget(logger, parent=self), "Muon Velocity")
        self.tab_widget.velocitywidget = self.tab_widget.widget(3)

        add_widget("velocity", self.tab_widget.widget(3))

        self.tab_widget.addTab(StatusWidget(logger, parent=self), "Status")
        self.tab_widget.statuswidget = self.tab_widget.widget(4)

        add_widget("status", self.tab_widget.widget(4))

        self.tab_widget.addTab(DAQWidget(logger, parent=self), "DAQ Output")
        self.tab_widget.daqwidget = self.tab_widget.widget(5)

        add_widget("daq", self.tab_widget.widget(5))

        self.tab_widget.addTab(GPSWidget(logger, parent=self), "GPS Output")
        self.tab_widget.gpswidget = self.tab_widget.widget(6)

        add_widget("gps", self.tab_widget.widget(6))

        # widgets which should be calculated in processIncoming.
        # The widget is only calculated when it is set to active (True)
        #  via widget.active
        # only widgets which need pulses go here
        self.pulse_widgets = [self.tab_widget.pulseanalyzerwidget,
                              self.tab_widget.velocitywidget,
                              self.tab_widget.decaywidget]

        # widgets which shuld be dynmacally updated by the timer should be in this list
        self.dynamic_widgets = [self.tab_widget.decaywidget,
                                self.tab_widget.pulseanalyzerwidget,
                                self.tab_widget.velocitywidget,
                                self.tab_widget.ratewidget]

        self.setCentralWidget(self.tab_widget)

        self.timer = QtCore.QTimer()
        QtCore.QObject.connect(self.timer,
                               QtCore.SIGNAL("timeout()"),
                               self.process_incoming)

        self.widget_updater = QtCore.QTimer()
        QtCore.QObject.connect(self.widget_updater,
                               QtCore.SIGNAL("timeout()"),
                               self.widget_update)

        self.timewindow = opts.timewindow  # 5.0
        self.logger.info("Timewindow is %4.2f" % self.timewindow)

        self.setup_menus()

        self.process_incoming()

        self.timer.start(1000)
        self.widget_updater.start(self.timewindow * 1000)

    def setup_screen(self):
        desktop = QtGui.QDesktopWidget()
        screen_size = QtCore.QRectF(desktop.screenGeometry(
                desktop.primaryScreen()))
        screen_x = screen_size.x() + screen_size.width()
        screen_y = screen_size.y() + screen_size.height()
        self.logger.info("Screen with size %i x %i detected!" %
                         (screen_x, screen_y))

        # FIXME: make it configurable
        # now simply set to 1600 x 1200
        if screen_x * screen_y >= 1920000:
            LargeScreenMPStyle()

    def setup_menus(self):
        # create the menubar
        menu_bar = self.menuBar()

        # create file menu
        file_menu = menu_bar.addMenu('&File')

        exit_action = QtGui.QAction(QtGui.QIcon('/usr/share/icons/gnome/24x24/actions/exit.png'), 'Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        self.connect(exit_action, QtCore.SIGNAL('triggered()'), QtCore.SLOT('close()'))

        file_menu.addAction(exit_action)

        # create settings menu
        settings_menu = menu_bar.addMenu('&Settings')

        config_action = QtGui.QAction('Channel Configuration', self)
        config_action.setStatusTip('Configure the Coincidences and channels')
        self.connect(config_action, QtCore.SIGNAL('triggered()'), self.config_menu)

        thresholds_action = QtGui.QAction('Thresholds', self)
        thresholds_action.setStatusTip('Set trigger thresholds')
        self.connect(thresholds_action, QtCore.SIGNAL('triggered()'), self.threshold_menu)

        advanced_action = QtGui.QAction('Advanced Configurations', self)
        advanced_action.setStatusTip('Advanced configurations')
        self.connect(advanced_action, QtCore.SIGNAL('triggered()'), self.advanced_menu)

        settings_menu.addAction(config_action)
        settings_menu.addAction(thresholds_action)
        settings_menu.addAction(advanced_action)

        # create help menu
        help_menu = menu_bar.addMenu('&Help')

        manualdoc_action = QtGui.QAction('Website with Manual', self)
        self.connect(manualdoc_action, QtCore.SIGNAL('triggered()'), self.manualdoc_menu)

        sphinxdoc_action = QtGui.QAction('Technical documentation', self)
        self.connect(sphinxdoc_action, QtCore.SIGNAL('triggered()'), self.sphinxdoc_menu)

        commands_action = QtGui.QAction('DAQ Commands', self)
        self.connect(commands_action, QtCore.SIGNAL('triggered()'), self.help_menu)

        about_action = QtGui.QAction('About muonic', self)
        self.connect(about_action, QtCore.SIGNAL('triggered()'), self.about_menu)

        help_menu.addAction(manualdoc_action)
        help_menu.addAction(commands_action)
        help_menu.addAction(sphinxdoc_action)
        help_menu.addAction(about_action)

    # the individual menus
    def threshold_menu(self):
        """
        Shows the threshold dialogue
        """
        # get the actual Thresholds...
        self.daq.put('TL')
        # wait explicitely till the thresholds get loaded
        self.logger.info("loading threshold information..")
        time.sleep(1.5)
        threshold_window = ThresholdDialog([self.threshold_ch0,
                                           self.threshold_ch1,
                                           self.threshold_ch2,
                                           self.threshold_ch3])
        rv = threshold_window.exec_()
        if rv == 1:
            commands = []
            for ch in ["0","1","2","3"]:
                val = threshold_window.get_widget_value("threshold_ch_" + ch)
                commands.append("TL " + ch + " " + str(val))
                
            for cmd in commands:
                self.daq.put(cmd)
                self.logger.info("Set threshold of channel %s to %s" %(cmd.split()[1],cmd.split()[2]))

        self.daq.put('TL')
  
    def config_menu(self):
        """
        Show the config dialog
        """
        gatewidth = 0.
        # get the actual channels...
        self.daq.put('DC')
        # wait explicitely till the channels get loaded
        self.logger.info("loading channel information...")
        time.sleep(1)

        config_window = ConfigDialog([self.channelcheckbox_0,
                                      self.channelcheckbox_1,
                                      self.channelcheckbox_2,
                                      self.channelcheckbox_3],
                                     [self.coincidencecheckbox_0,
                                      self.coincidencecheckbox_1,
                                      self.coincidencecheckbox_2,
                                      self.coincidencecheckbox_3],
                                     self.vetocheckbox,
                                     [self.vetocheckbox_0,
                                      self.vetocheckbox_1,
                                      self.vetocheckbox_2])
        rv = config_window.exec_()
        if rv == 1:
            chan0_active = config_window.get_widget_value("channel_checkbox_0")
            chan1_active = config_window.get_widget_value("channel_checkbox_1")
            chan2_active = config_window.get_widget_value("channel_checkbox_2")
            chan3_active = config_window.get_widget_value("channel_checkbox_3")
            singles = config_window.get_widget_value("coincidence_checkbox_0")
            # if singles:
            #    self.tabwidget.ratewidget.hide_trigger = True
            # else:
            self.tab_widget.ratewidget.hide_trigger = False
            
            twofold = config_window.get_widget_value("coincidence_checkbox_1")
            threefold = config_window.get_widget_value("coincidence_checkbox_2")
            fourfold = config_window.get_widget_value("coincidence_checkbox_3")

            veto = config_window.get_widget_value("veto_checkbox")
            vetochan1 = config_window.get_widget_value("veto_checkbox_0")
            vetochan2 = config_window.get_widget_value("veto_checkbox_1")
            vetochan3 = config_window.get_widget_value("veto_checkbox_2")
            
            tmp_msg = ''
            if veto:
                if vetochan1:
                    tmp_msg += '01'
                elif vetochan2:
                    tmp_msg += '10'
                elif vetochan3:
                    tmp_msg += '11'
                else:
                    tmp_msg += '00' 
            else:
                tmp_msg += '00'
    
            coincidence_set = False
            for coincidence in [(singles, '00'), (twofold, '01'), (threefold, '10'), (fourfold, '11')]:
                if coincidence[0]:
                    tmp_msg += coincidence[1]
                    coincidence_set = True
            
            # else case, just in case
            if not coincidence_set:
                tmp_msg += '00'
    
            # now calculate the correct expression for the first
            # four bits
            self.logger.debug("The first four bits are set to %s" % tmp_msg)
            msg = 'WC 00 ' + hex(int(''.join(tmp_msg), 2))[-1].capitalize()
    
            channel_set = False
            enable = ['0', '0', '0', '0']
            for channel in enumerate([chan3_active, chan2_active, chan1_active, chan0_active]):
                if channel[1]:
                    enable[channel[0]] = '1'
                    channel_set = True
            
            if not channel_set:
                msg += '0'
                
            else:
                msg += hex(int(''.join(enable), 2))[-1].capitalize()
            
            self.daq.put(msg)
            self.logger.info('The following message was sent to DAQ: %s' % msg)

            self.logger.debug('channel0 selected %s' % chan0_active)
            self.logger.debug('channel1 selected %s' % chan1_active)
            self.logger.debug('channel2 selected %s' % chan2_active)
            self.logger.debug('channel3 selected %s' % chan3_active)
            self.logger.debug('coincidence singles %s' % singles)
            self.logger.debug('coincidence twofold %s' % twofold)
            self.logger.debug('coincidence threefold %s' % threefold)
            self.logger.debug('coincidence fourfold %s' % fourfold)
        self.daq.put('DC')
           
    def advanced_menu(self):
        """
        Show a config dialog for advanced options, ie. gatewidth, interval for the rate measurement, options for writing pulsefile and the nostatus option
        """
        gatewidth = 0.
        # get the actual channels...
        self.daq.put('DC')
        # wait explicitely till the channels get loaded
        self.logger.info("loading channel information...")
        time.sleep(1)

        adavanced_window = AdvancedDialog(self.coincidence_time, self.timewindow, self.nostatus)
        rv = adavanced_window.exec_()
        if rv == 1:
            _timewindow = float(adavanced_window.get_widget_value("time_window"))
            _gatewidth = bin(int(adavanced_window.get_widget_value("gate_width"))/10).replace('0b','').zfill(16)
            _nostatus = adavanced_window.get_widget_value("write_status")
            
            _03 = format(int(_gatewidth[0:8],2),'x').zfill(2)
            _02 = format(int(_gatewidth[8:16],2),'x').zfill(2)
            tmp_msg = 'WC 03 '+str(_03)
            self.daq.put(tmp_msg)
            tmp_msg = 'WC 02 '+str(_02)
            self.daq.put(tmp_msg)
            if _timewindow < 0.01 or _timewindow > 10000.:
                self.logger.warning("Timewindow too small or too big, resetting to 5 s.")
                self.timewindow = 5.0
            else:
                self.timewindow = _timewindow
            self.widget_updater.start(self.timewindow * 1000)
            self.nostatus = not _nostatus

            self.logger.debug('Writing gatewidth WC 02 %s WC 03 %s' % (_02, _03))
            self.logger.debug('Setting timewindow to %.2f ' % _timewindow)
            self.logger.debug('Switching nostatus option to %s' % _nostatus)

        self.daq.put('DC')

    @staticmethod
    def help_menu():
        """
        Show a simple help menu
        """
        help_window = HelpDialog()
        help_window.exec_()
        
    def about_menu(self):
        """
        Show a link to the online documentation
        """
        QtGui.QMessageBox.information(self, "about muonic",
                                      "version: %s\n source located at: %s" %
                                      (__version__, __source_location__))

    def sphinxdoc_menu(self):
        """
        Show the sphinx documentation that comes with muonic in a
        browser
        """
        #docs = (os.path.join(DOCPATH,"index.html"))
        docs = __docs_hosted_at__
        self.logger.debug("Opening docs from %s" %docs)
        success = webbrowser.open(docs)
        if not success:
            self.logger.warning("Can not open webbrowser! Browse to %s to see the docs" %docs)

    def manualdoc_menu(self):
        """
        Show the manual that comes with muonic in a pdf viewer
        """
        #docs = (os.path.join(DOCPATH,"manual.pdf"))
        docs = __manual_hosted_at__

        self.logger.info("opening docs from %s" %docs)
        success = webbrowser.open(docs)
        if not success:
            self.logger.warning("Can not open PDF reader!")

    def get_thresholds_from_queue(self, msg):
        """
        Explicitely scan message for threshold information
        Return True if found, else False
        """
        if msg.startswith('TL') and len(msg) > 9:
            msg = msg.split('=')
            self.threshold_ch0 = int(msg[1][:-2])
            self.threshold_ch1 = int(msg[2][:-2])
            self.threshold_ch2 = int(msg[3][:-2])
            self.threshold_ch3 = int(msg[4])
            self.logger.debug("Got Thresholds %i %i %i %i" %
                              (self.threshold_ch0, self.threshold_ch1,
                               self.threshold_ch2, self.threshold_ch3))

            # update_setting("threshold_ch0", int(msg[1][:-2]))
            # update_setting("threshold_ch1", int(msg[2][:-2]))
            # update_setting("threshold_ch2", int(msg[3][:-2]))
            # update_setting("threshold_ch3", int(msg[4]))
            # self.logger.debug("Got Thresholds %d %d %d %d" %
            #                   tuple([get_setting("threshold_ch%d" % i)
            #                          for i in range(4)]))
            return True
        else:
            return False
        
    def get_channels_from_queue(self, msg):
        """
        Explicitely scan message for channel information
        Return True if found, else False

        DC gives :
        DC C0=23 C1=71 C2=0A C3=00
        
        Which has the meaning:

        MM - 00 -> 8bits for channel enable/disable, coincidence and veto
        |7   |6   |5          |4          |3       |2       |1 |0       |
        |veto|veto|coincidence|coincidence|channel3|channel2|channel1|channel0|
        ---------------------------bits-------------------------------------
        Set bits for veto:
        ........................
        00 - ch0 is veto
        01 - ch1 is veto
        10 - ch2 is veto
        11 - ch3 is veto
        ........................
        Set bits for coincidence
        ........................
        00 - singles
        01 - twofold
        10 - threefold
        11 - fourfold
        """
        if msg.startswith('DC ') and len(msg) > 25:
            msg = msg.split(' ')
            self.coincidence_time = msg[4].split('=')[1]+ msg[3].split('=')[1]
            msg = bin(int(msg[1][3:], 16))[2:].zfill(8)
            vetoconfig = msg[0:2]
            coincidenceconfig = msg[2:4]
            channelconfig = msg[4:8]

            self.coincidence_time = int(self.coincidence_time, 16)*10

            # coincidence_time = msg[4].split('=')[1]+ msg[3].split('=')[1]
            # msg = bin(int(msg[1][3:], 16))[2:].zfill(8)
            # veto_config = msg[0:2]
            # coincidence_config = msg[2:4]
            # channel_config = msg[4:8]

            # update_setting("coincidence_time",
            #                int(coincidence_time, 16) * 10)
            
            self.vetocheckbox_0 = False
            self.vetocheckbox_1 = False
            self.vetocheckbox_2 = False
            self.vetocheckbox = True

            # # set veto checkboxes
            # for i in range(4):
            #     if i == 0:
            #         update_setting("veto", True)
            #     else:
            #         update_setting("veto_ch%d" % i, False)

            if str(channelconfig[3]) == '0':
                self.channelcheckbox_0 = False
            else:
                self.channelcheckbox_0 = True

            if str(channelconfig[2]) == '0':
                self.channelcheckbox_1 = False
            else:
                self.channelcheckbox_1 = True

            if str(channelconfig[1]) == '0':
                self.channelcheckbox_2 = False
            else:
                self.channelcheckbox_2 = True
            if str(channelconfig[0]) == '0':
                self.channelcheckbox_3 = False
            else:
                self.channelcheckbox_3 = True
            if str(coincidenceconfig) == '00':
                self.coincidencecheckbox_0 = True
            else:
                self.coincidencecheckbox_0 = False
            if str(coincidenceconfig) == '01':
                self.coincidencecheckbox_1 = True
            else:
                self.coincidencecheckbox_1 = False
            if str(coincidenceconfig) == '10':
                self.coincidencecheckbox_2 = True
            else:
                self.coincidencecheckbox_2 = False

            if str(coincidenceconfig) == '11':
                self.coincidencecheckbox_3 = True
            else:
                self.coincidencecheckbox_3 = False

            # # update channel config
            # for i in range(4):
            #     update_setting("active_ch%d" % i,
            #                    channel_config[3 - i] == '1')
            #
            # # update coincidence config
            # for i, seq in enumerate(['00', '01', '10', '11']):
            #     update_setting("coincidence%d" % i,
            #                    coincidence_config == seq)

            if str(vetoconfig) == '00':
                self.vetocheckbox = False
            else:
                if str(vetoconfig) == '01': self.vetocheckbox_0 = True
                if str(vetoconfig) == '10': self.vetocheckbox_1 = True
                if str(vetoconfig) == '11': self.vetocheckbox_2 = True

            # # update veto config
            # for i, seq in enumerate(['00', '01', '10', '11']):
            #     if veto_config == seq:
            #         if i == 0:
            #             update_setting("veto", False)
            #         else:
            #             update_setting("veto_ch%d" % i, True)

            self.logger.debug('Coincidence timewindow %s ns' %(str(self.coincidence_time)))
            self.logger.debug("Got channel configurations: %i %i %i %i" %(self.channelcheckbox_0,self.channelcheckbox_1,self.channelcheckbox_2,self.channelcheckbox_3))
            self.logger.debug("Got coincidence configurations: %i %i %i %i" %(self.coincidencecheckbox_0,self.coincidencecheckbox_1,self.coincidencecheckbox_2,self.coincidencecheckbox_3))
            self.logger.debug("Got veto configurations: %i %i %i %i" %(self.vetocheckbox,self.vetocheckbox_0,self.vetocheckbox_1,self.vetocheckbox_2))

            # self.logger.debug('Coincidence timewindow %d ns' %
            #                   get_setting("coincidence_time"))
            # self.logger.debug("Got channel configurations: %d %d %d %d" %
            #                   tuple([get_setting("active_ch%d" % i)
            #                          for i in range(4)]))
            # self.logger.debug("Got coincidence configurations: %d %d %d %d" %
            #                   tuple([get_setting("coincidence%d" % i)
            #                          for i in range(4)]))
            # self.logger.debug("Got veto configurations: %d %d %d %d" %
            #                   tuple([get_setting("veto")] +
            #                         [get_setting("veto_ch%d" % i)
            #                          for i in range(3)]))

            return True
        else:
            return False

    # this functions gets everything out of the daq
    # All calculations should happen here
    def process_incoming(self):
        """
        Handle all the messages currently in the daq 
        and pass the result to the corresponding widgets
        """
        while self.daq.data_available():

            try:
                msg = self.daq.get(0)
            except DAQIOError:
                self.logger.debug("Queue empty!")
                return None

            self.daq_msg = msg #make it public for daughters
            # Check contents of message and do what it says         
            daq_widget = get_widget("daq")
            daq_widget.calculate()
            
            gps_widget = get_widget("gps")

            if (gps_widget.active() and
                    gps_widget.isEnabled()):
                if len(gps_widget.gps_dump) <= gps_widget.read_lines:
                    gps_widget.gps_dump.append(msg)
                if len(gps_widget.gps_dump) == gps_widget.read_lines:
                    gps_widget.calculate()
                continue
                
            status_widget = get_widget("status")

            if status_widget.isVisible() and status_widget.active():
                status_widget.update()

            decay_widget = get_widget("decay")

            if msg.startswith('DC') and len(msg) > 2 and decay_widget.active():
                try:
                    split_msg = msg.split(" ")
                    decay_widget.previous_coinc_time_03 = split_msg[4].split("=")[1]
                    decay_widget.previous_coinc_time_02 = split_msg[3].split("=")[1]
                except:
                    self.logger.debug('Wrong DC command.')
                continue

            # check for threshold information
            if self.get_thresholds_from_queue(msg):
                continue

            if self.get_channels_from_queue(msg):
                continue

            # status messages
            if msg.startswith('ST') or len(msg) < 50:
                continue

            rate_widget = get_widget("rate")

            if rate_widget.calculate():
                continue

            pulse_widget = get_widget("pulse")
            velocity_widget = get_widget("velocity")
            
            if (decay_widget.active() or pulse_widget.active() or
                    self.pulsefilename or velocity_widget.active()):
                self.pulses = self.pulseextractor.extract(msg)

            self.widget_calculate()

    def widget_calculate(self):
        """
        Starts the widgets calculate function inside the processIncoming.
        Set active flag (second parameter in the calculate_widgets list) to
        True if it should run only when the widget is active.
        """
        for widget in self.pulse_widgets:
            if widget.active() and (self.pulses is not None):
                widget.calculate()

    def widget_update(self):
        """
        Update the widgets
        """
        for widget in self.dynamic_widgets:
            if widget.active():
                widget.update()

    def closeEvent(self, ev):
        """
        Is triggered when the window is closed, we have to reimplement it
        to provide our special needs for the case the program is ended.
        """

        self.logger.info('Attempting to close Window!')
        # ask kindly if the user is really sure if she/he wants to exit
        reply = QtGui.QMessageBox.question(self, 'Attention!',
                'Do you really want to exit?', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            self.timer.stop()
            self.widget_updater.stop()
            now = datetime.datetime.now()

            # close the RAW file (if any)
            if self.tab_widget.daqwidget.write_file:
                self.tab_widget.daqwidget.write_file = False
                mtime = now - self.raw_mes_start
                mtime = round(mtime.seconds/(3600.),2) + mtime.days*24
                self.logger.info("The raw data was written for %f hours" % mtime)
                newrawfilename = self.rawfilename.replace("HOURS",str(mtime))
                shutil.move(self.rawfilename,newrawfilename)
                self.tab_widget.daqwidget.outputfile.close()

            if self.tab_widget.decaywidget.active():
                mtime = now - self.tab_widget.decaywidget.dec_mes_start
                mtime = round(mtime.seconds/(3600.),2) + mtime.days*24
                self.logger.info("The muon decay measurement was active for %f hours" % mtime)
                newmufilename = self.decayfilename.replace("HOURS",str(mtime))
                shutil.move(self.decayfilename,newmufilename)

            if self.pulsefilename:
                old_pulsefilename = self.pulsefilename
                # no pulses shall be extracted any more, 
                # this means changing lots of switches
                self.pulsefilename = False
                self.showpulses = False
                self.pulseextractor.close_file()
                mtime = now - self.pulse_mes_start
                mtime = round(mtime.seconds/(3600.),2) + mtime.days*24
                self.logger.info("The pulse extraction measurement was active for %f hours" % mtime)
                newpulsefilename = old_pulsefilename.replace("HOURS",str(mtime))
                shutil.move(old_pulsefilename,newpulsefilename)

            try:
                self.tab_widget.ratewidget.data_file_write = False
                self.tab_widget.ratewidget.data_file.close()
            except (AttributeError, IOError):
                pass
            
            mtime = now - self.tab_widget.ratewidget.measurement_start
            #print 'HOURS ', now, '|', mtime, '|', mtime.days, '|', str(mtime)                
            mtime = round(mtime.seconds/(3600.),2) + mtime.days*24
            #print 'new mtime ', mtime, str(mtime)
            self.logger.info("The rate measurement was active for %f hours" % mtime)
            newratefilename = self.filename.replace("HOURS",str(mtime))
            #print 'new raw name', newratefilename
            shutil.move(self.filename,newratefilename)
            time.sleep(0.5)
            self.tab_widget.writefile = False
            try:
                self.tab_widget.decaywidget.mu_file.close()
 
            except AttributeError:
                pass

            self.emit(QtCore.SIGNAL('lastWindowClosed()'))
            self.close()

        else: # don't close the mainwindow
            ev.ignore()
