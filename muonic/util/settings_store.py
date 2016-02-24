"""
Global application settings
"""

__all__ = ["update_setting", "have_setting", "get_setting",
           "remove_setting", "update_settings"]

_default_settings = {
    "write_pulses": False,
    "write_daq_status": False,
    "time_window": 5.0,
    "coincidence_time": 0.0,
    "veto": False,
    "veto_ch0": False,
    "veto_ch1": False,
    "veto_ch2": False,
    "veto_ch3": False,
    "active_ch0": True,
    "active_ch1": True,
    "active_ch2": True,
    "active_ch3": True,
    "coincidence0": True,
    "coincidence1": False,
    "coincidence2": False,
    "coincidence3": False
}

_settings = dict()


def update_setting(key, value):
    """
    Update value for settings key.

    :param key: settings key
    :type key: str
    :param value: setting value
    :type value: object
    :returns: None
    """
    global _settings

    if key is not None:
        _settings[key] = value


def have_setting(key):
    """
    Returns true if settings key exists, False otherwise.

    :param key: settings key
    :type key: str
    :returns: bool
    """
    return key in _settings


def get_setting(key):
    """
    Retrieves the settings value for given key.

    :param key: settings key
    :type key: str
    :returns: object
    """
    return _settings.get(key)


def remove_setting(key):
    """
    Remove setting with key.

    :param key: settings key
    :type key: str
    :returns: removed object
    """
    return _settings.pop(key)


def update_settings(settings):
    """
    Add settings from dict.

    :param settings: settings dictionary
    :type settings: dict
    :returns: None
    """
    if settings is None:
        return
    if isinstance(settings, dict):
        for key, value in list(settings.items()):
            update_setting(key, value)
    else:
        raise TypeError("argument has to be a dict")


def apply_default_settings():
    """
    Apply default settings. Settings keys different from the default settings
    will retain.

    :returns: None
    """
    update_settings(_default_settings)
