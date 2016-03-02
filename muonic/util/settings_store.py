"""
Global application settings store
"""
from __future__ import print_function

__all__ = ["update_setting", "have_setting", "get_setting",
           "remove_setting", "update_settings",
           "apply_default_settings", "dump_settings"]

_default_settings = {
    "write_pulses": False,
    "write_daq_status": False,
    "time_window": 5.0,
    "gate_width": 0.0,
    "veto": False,
    "veto_ch0": False,
    "veto_ch1": False,
    "veto_ch2": False,
    "active_ch0": True,
    "active_ch1": True,
    "active_ch2": True,
    "active_ch3": True,
    "coincidence0": True,
    "coincidence1": False,
    "coincidence2": False,
    "coincidence3": False,
    "threshold_ch0": 300,
    "threshold_ch1": 300,
    "threshold_ch2": 300,
    "threshold_ch3": 300
}

_settings = dict()


def update_setting(key, value):
    """
    Update value for settings key.

    Raises KeyError if key is None.

    :param key: settings key
    :type key: str
    :param value: setting value
    :type value: object
    :raises: KeyError
    :returns: None
    """
    global _settings

    if key is None:
        raise KeyError("key must not be of 'None-Type'")

    _settings[key] = value


def have_setting(key):
    """
    Returns true if settings key exists, False otherwise.

    :param key: settings key
    :type key: str
    :returns: bool
    """
    return key in _settings


def get_setting(key, default=None):
    """
    Retrieves the settings value for given key.

    :param key: settings key
    :type key: str
    :param default: the default value if setting is not found
    :type default: mixed
    :returns: object
    """
    return _settings.get(key, default)


def remove_setting(key):
    """
    Remove setting with key.

    :param key: settings key
    :type key: str
    :returns: removed object
    """
    return _settings.pop(key)


def clear_settings():
    """
    Clears the settings store

    :returns: None
    """
    _settings.clear()


def update_settings(settings, clear=False):
    """
    Add settings from dict.

    :param settings: settings dictionary
    :type settings: dict
    :param clear: clear settings store before updating settings
    :type clear: bool
    :returns: None
    """
    if settings is None:
        return
    if isinstance(settings, dict):
        if clear:
            clear_settings()
        for key, value in list(settings.items()):
            update_setting(key, value)
    else:
        raise TypeError("argument has to be a dict")


def apply_default_settings(clear=False):
    """
    Apply default settings. If 'clear' is False settings keys
    different from the default settings will retain.

    :param clear: clear settings store before applying default settings
    :type clear: bool
    :returns: None
    """
    update_settings(_default_settings, clear)


def dump_settings():
    """
    Prints the current settings.

    :returns: None
    """
    for key, value in sorted(_settings.items()):
        print("%-20s = %s" % (key, value))
