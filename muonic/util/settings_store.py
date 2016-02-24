"""
Global application settings
"""

__all__ = ["update_setting", "have_setting", "get_setting",
           "remove_setting", "update_settings"]

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
        raise TypeError("argmument has to be a dict")