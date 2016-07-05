"""
Provide the dialog fields for user interaction
"""

from os import path

from PyQt4 import QtCore, QtGui


class BaseDialog(QtGui.QDialog):
    """
    Abstract base class for all dialogs

    :param window_title: the title of the window
    :type window_title: str
    """
    DEFAULT_ITEM_LABELS = ["Chan0", "Chan1", "Chan2", "Chan3"]
    
    def __init__(self, window_title):
        QtGui.QDialog.__init__(self)
        self.setWindowTitle(window_title)
        self.setModal(True)

    def get_widget_value(self, object_name):
        """
        Get the value of a widget by its object name.

        :param object_name: the object name of the widget
        :type: str
        :return: mixed
        """
        widget = self.findChild(QtGui.QWidget, object_name)

        if widget is not None:
            if (isinstance(widget, QtGui.QRadioButton) or
                    isinstance(widget, QtGui.QCheckBox) or
                    isinstance(widget, QtGui.QGroupBox)):
                return widget.isChecked()
            elif (isinstance(widget, QtGui.QSpinBox) or
                    isinstance(widget, QtGui.QDoubleSpinBox)):
                return widget.value()
            elif isinstance(widget, QtGui.QLineEdit):
                return widget.text()
        return None
    
    def button_box(self, left=80, top=900):
        """
        Create a custom button for cancel/apply.

        :param left: left offset
        :type left: int
        :param top: top offset
        :type top: int
        """
        box = QtGui.QDialogButtonBox(self)
        box.setGeometry(QtCore.QRect(left, top, 300, 32))
        box.setOrientation(QtCore.Qt.Horizontal)
        box.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                               QtGui.QDialogButtonBox.Ok)

        QtCore.QObject.connect(box, QtCore.SIGNAL('accepted()'), self.accept)
        QtCore.QObject.connect(box, QtCore.SIGNAL('rejected()'), self.reject)

        return box

    def choice_group(self, object_name="object", label="label",
                     checkable=False, checked=False, radio=False,
                     checked_items=None, item_labels=None, left=20):
        """
        Create a group of choices.

        :param object_name: the base object name for the checkbox group.
            checkboxes get named 'object_name_%d' where %d is
            the checkboxes' index
        :type object_name: str
        :param label: the label of the checkbox group
        :type label: str
        :param checkable: determined if the group box itself is checkable
        :type checkable: bool
        :param checked: initial state of the checkable group box
        :type checked: bool
        :param radio: create radio buttons instead of check boxes
        :type radio: bool
        :param checked_items: items that are checked initially
        :type checked_items: list of int
        :param item_labels: labels of the checkboxes/radio buttons
        :type item_labels: list
        :param left: left offset
        :type left: int
        """
        if item_labels is None:
            item_labels = self.DEFAULT_ITEM_LABELS

        layout = QtGui.QVBoxLayout()

        layout.addStretch(1)

        group_box = QtGui.QGroupBox(label)
        group_box.setCheckable(checkable)
        group_box.setChecked(checked)
        group_box.setObjectName(object_name)
        group_box.setLayout(layout)

        for index, label in enumerate(item_labels):
            if radio:
                check_box = QtGui.QRadioButton(self)
            else:
                check_box = QtGui.QCheckBox(self)
            check_box.setGeometry(QtCore.QRect(left, 40 + index * 40, 119, 28))
            check_box.setObjectName("%s_%d" % (object_name, index))
            check_box.setText(label)
 
            if checked_items is not None and index in checked_items:
                check_box.setChecked(True)

            layout.addWidget(check_box)

        return group_box


class DecayConfigDialog(BaseDialog):
    """
    Settings for the muondecay
    """
    
    def __init__(self):
        BaseDialog.__init__(self, "Muon Decay Configuration")

        layout = QtGui.QGridLayout(self)

        layout.addWidget(self.choice_group(radio=True, label="Single Pulse",
                                           object_name="single_checkbox",
                                           checked_items=[1], left=20), 0, 0)
        layout.addWidget(self.choice_group(radio=True, label="Double Pulse",
                                           object_name="double_checkbox",
                                           checked_items=[2], left=180), 0, 1)
        layout.addWidget(self.choice_group(radio=True,
                                           label="Software Veto Channel",
                                           object_name="veto_checkbox",
                                           checked_items=[3], left=300), 0, 2)

        min_time_spinbox = QtGui.QSpinBox()
        min_time_spinbox.setObjectName("min_pulse_time")
        min_time_spinbox.setMaximum(2000)
        min_time_spinbox.setValue(400)
        min_time_spinbox.setToolTip("Reject events where the double pulses " +
                                    "are too close together")

        layout.addWidget(min_time_spinbox, 2, 0)
        layout.addWidget(QtGui.QLabel("Minimum time between\n" +
                                      "two pulses (in ns)"), 2, 1)

        pulse_width_group_box = QtGui.QGroupBox("Set conditions on " +
                                                "pulse width")
        pulse_width_group_box.setCheckable(True)
        pulse_width_group_box.setChecked(False)
        pulse_width_group_box.setObjectName("set_pulse_width_conditions")

        pulse_width_layout = QtGui.QGridLayout(pulse_width_group_box)

        pulse_width_items = [
            {
                'object_name': 'min_single_pulse_width',
                'label': 'Min mu pulse width',
                'tooltip': 'Define a MINIMUM width for the MUON pulse',
                'value': 10
            }, {
                'object_name': 'max_single_pulse_width',
                'label': 'Max mu pulse width',
                'tooltip': 'Define a MAXIMUM width for the MUON pulse',
                'value': 300
            }, {
                'object_name': 'min_double_pulse_width',
                'label': 'Min e pulse width',
                'tooltip': 'Define a MINIMUM width for the ELECTRON pulse',
                'value': 5
            }, {
                'object_name': 'max_double_pulse_width',
                'label': 'Max e pulse width',
                'tooltip': 'Define a MINIMUM width for the ELECTRON pulse',
                'value': 300
            }
        ]

        for i, item in enumerate(pulse_width_items):
            spinbox = QtGui.QSpinBox()
            spinbox.setObjectName(item['object_name'])
            spinbox.setSuffix(' ns')
            spinbox.setValue(item['value'])
            spinbox.setToolTip(item['tooltip'])
            spinbox.setMaximum(11000)
            pulse_width_layout.addWidget(spinbox, i, 0)
            pulse_width_layout.addWidget(QtGui.QLabel(item['label']), i, 1)

        layout.addWidget(pulse_width_group_box, 3, 0, 1, 3)
        layout.addWidget(self.button_box(left=200), 4, 2)

        self.show()


class FitRangeConfigDialog(BaseDialog):
    """
    Dialog to configure the fit range

    :param upper_lim: upper limits for the fit
    :type: tuple of float
    :param lower_lim: lower limits for the fit
    :type: tuple of float
    :param dimension: suffix
    :type dimension: str
    """

    def __init__(self, upper_lim=None, lower_lim=None, dimension=''):
        BaseDialog.__init__(self, "Fit Range Configuration")

        layout = QtGui.QGridLayout(self)

        lower = QtGui.QDoubleSpinBox()
        lower.setDecimals(2)
        lower.setSingleStep(0.01)
        lower.setObjectName("lower_limit")
        lower.setSuffix(' %s' % dimension)

        if lower_lim:
            lower.setMinimum(lower_lim[0])
            lower.setMaximum(lower_lim[1])
            lower.setValue(lower_lim[2])

        layout.addWidget(QtGui.QLabel("Lower limit for the fit range: "), 0, 0)
        layout.addWidget(lower, 0, 1)

        upper = QtGui.QDoubleSpinBox()
        upper.setDecimals(2)
        upper.setSingleStep(0.01)
        upper.setObjectName("upper_limit")
        upper.setSuffix(' %s' % dimension)

        if upper_lim:
            upper.setMinimum(upper_lim[0])
            upper.setMaximum(upper_lim[1])
            upper.setValue(upper_lim[2])

        layout.addWidget(QtGui.QLabel("Upper limit for the fit range: "), 1, 0)
        layout.addWidget(upper, 1, 1)
        layout.addWidget(self.button_box(left=200), 2, 0, 2, 0)

        self.show()


class VelocityConfigDialog(BaseDialog):
    """
    Dialog to configure the muon velocity
    """

    def __init__(self):
        BaseDialog.__init__(self, "Muon Velocity Configuration")

        layout = QtGui.QGridLayout(self)
        layout.addWidget(self.choice_group(radio=True, label="Upper Channel",
                                           object_name="upper_checkbox",
                                           checked_items=[0], left=20), 0, 0)
        layout.addWidget(self.choice_group(radio=True, label="Lower Channel",
                                           object_name="lower_checkbox",
                                           checked_items=[1], left=180), 0, 1)
        layout.addWidget(self.button_box(left=200), 1, 1)

        self.show()


class ThresholdDialog(BaseDialog):
    """
    Dialog to adjust the thresholds

    :param thresholds: the threshold for the four channels
    :type thresholds: list of int
    """

    def __init__(self, thresholds):
        BaseDialog.__init__(self, "Thresholds")

        layout = QtGui.QVBoxLayout(self)

        for channel, threshold in enumerate(thresholds):
            spinbox = QtGui.QSpinBox()
            spinbox.setMaximum(1000)
            spinbox.setObjectName("threshold_ch_%d" % channel)
            spinbox.setValue(int(threshold))
            spinbox.setSuffix(' mV')
            layout.addWidget(QtGui.QLabel("Channel %d" % channel))
            layout.addWidget(spinbox)
                        
        layout.addWidget(self.button_box(left=0))

        self.show()


class ConfigDialog(BaseDialog):
    """
    Dialog to set the configuration

    :param channel_states: activation states of the channels
    :type channel_states: list of bool
    :param coincidence_states: coincidence states
    :type coincidence_states: list of bool
    :param veto_enabled: enable veto group
    :type veto_enabled: bool
    :param channel_veto_states: channel veto
    :type channel_veto_states: list of bool
    """
    DEFAULT_CHANNEL_STATES = [True] * 4
    DEFAULT_COINCIDENCE_STATES = [True] + [False] * 3
    DEFAULT_CHANNEL_VETO_STATES = [False] * 3
    
    def __init__(self, channel_states=DEFAULT_CHANNEL_STATES,
                 coincidence_states=DEFAULT_COINCIDENCE_STATES,
                 veto_enabled=False,
                 channel_veto_states=DEFAULT_CHANNEL_VETO_STATES):
        BaseDialog.__init__(self, "Channel Configuration")

        checked_channels = []
        checked_coincidences = []
        checked_channel_vetos = []

        for _channel, checked in enumerate(channel_states):
            if checked:
                checked_channels.append(_channel)

        for _coincidence, checked in enumerate(coincidence_states):
            if checked:
                checked_coincidences.append(_coincidence)

        for _veto, checked in enumerate(channel_veto_states):
            if checked:
                checked_channel_vetos.append(_veto)

        layout = QtGui.QGridLayout(self)
        layout.addWidget(
                self.choice_group(label="Select Channel",
                                  object_name="channel_checkbox",
                                  checked_items=checked_channels,
                                  left=300), 0, 0)
        layout.addWidget(
                self.choice_group(radio=True, label="Trigger Condition",
                                  object_name="coincidence_checkbox",
                                  checked_items=checked_coincidences,
                                  item_labels=["Single", "Twofold",
                                               "Threefold", "Fourfold"],
                                  left=20), 0, 1)
        layout.addWidget(
                self.choice_group(radio=True, label="Veto",
                                  checkable=True, checked=veto_enabled,
                                  object_name="veto_checkbox",


                                  checked_items=checked_channel_vetos,
                                  item_labels=["Chan1", "Chan2", "Chan3"],
                                  left=180), 0, 2)
        layout.addWidget(self.button_box(left=30, top=300), 1, 2, 1, 2)

        self.show()


class AdvancedDialog(BaseDialog):
    """
    Dialog to set advanced configuration options.

    :param gate_width: the gate width of the time window
    :type gate_width: float
    :param time_window: the readout interval
    :type time_window: float
    :param write_daq_status: write DAQ status to raw file
    :type write_daq_status: bool
    """
    
    def __init__(self, gate_width=100, time_window=5.0,
                 write_daq_status=False):
        BaseDialog.__init__(self, "Advanced Configurations")

        layout = QtGui.QGridLayout(self)

        gate_width_box = QtGui.QSpinBox()
        gate_width_box.setSuffix(' ns')
        gate_width_box.setObjectName("gate_width")
        gate_width_box.setMaximum(159990)
        gate_width_box.setSingleStep(10)
        gate_width_box.setMinimum(10)
        gate_width_box.setValue(gate_width)
        gate_width_box.setToolTip("Define a gate width, which is the " +
                                  "time window opened by a trigger")

        layout.addWidget(QtGui.QLabel("Gate width time window " +
                                      "(default: 100 ns): "), 0, 0)
        layout.addWidget(gate_width_box, 0, 1)

        time_window_box = QtGui.QDoubleSpinBox()
        time_window_box.setDecimals(1)
        time_window_box.setSingleStep(0.1)
        time_window_box.setSuffix(' s')
        time_window_box.setObjectName("time_window")
        time_window_box.setMaximum(1000)
        time_window_box.setMinimum(0.01)
        time_window_box.setValue(time_window)
        time_window_box.setToolTip("Define an interval for calculating " +
                                   "and refreshing the rates.")

        layout.addWidget(QtGui.QLabel("Readout Interval " +
                                      "(default: 5 s): "), 1, 0)
        layout.addWidget(time_window_box, 1, 1)

        write_status_checkbox = QtGui.QCheckBox()
        write_status_checkbox.setObjectName("write_daq_status")
        write_status_checkbox.setChecked(write_daq_status)
        write_status_checkbox.setToolTip("Write DAQ status lines to RAW " +
                                         "file, same as option -n.")

        layout.addWidget(QtGui.QLabel("Write DAQ status lines to RAW file: "),
                         2, 0)
        layout.addWidget(write_status_checkbox, 2, 1)
        layout.addWidget(self.button_box(left=30, top=300), 3, 0, 1, 2)

        self.show()


class HelpDialog(BaseDialog):
    """
    Help Dialog for the DAQ commands
    """

    def __init__(self):
        BaseDialog.__init__(self, "DAQ Commands")
        self.resize(600, 480)

        help_file = path.join(path.dirname(__file__), 'daq_commands_help.txt')

        with open(help_file, 'r') as f:
            help_text = f.read()

        text_box = QtGui.QPlainTextEdit(help_text)
        text_box.setReadOnly(True)

        button_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok)
        QtCore.QObject.connect(button_box, QtCore.SIGNAL('accepted()'),
                               self.accept)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(text_box)
        layout.addWidget(button_box)

        self.show()

if __name__ == "__main__":
    import sys

    app = QtGui.QApplication(sys.argv)
    config_dialog = ConfigDialog()
    decay_dialog = DecayConfigDialog()
    threshold_dialog = ThresholdDialog([42, 42, 42, 42])
    velocity_dialog = VelocityConfigDialog()
    sys.exit(app.exec_())
