"""
Global application widget store
"""
from PyQt4 import QtGui

__all__ = ["add_widget", "have_widget", "get_widget",
           "remove_widget", "add_widgets"]

_widgets = dict()


def add_widget(name, widget):
    """
    Adds widget to the store.

    Raises WidgetWithNameExistsError if a wiiget of that name already exists
    and TypeError if widget is no subclass of QtGui.QWidget.

    :param name: widget name
    :type name: str
    :param widget: widget object
    :type widget: object
    :returns: None
    :raises: WidgetWithNameExistsError, TypeError
    """
    global _widgets

    if widget is None:
        return
    if have_widget(name):
        raise WidgetWithNameExistsError(
                "widget with name '%s' already exists" % name)
    else:
        if not isinstance(widget, QtGui.QWidget):
            raise TypeError("widget has to be a subclass 'QtGui.QWidget'")
        else:
            _widgets[name] = widget


def have_widget(name):
    """
    Returns true if widget with name exists, False otherwise.

    :param name: widget name
    :type name: str
    :returns: bool
    """
    return name in _widgets


def get_widget(name):
    """
    Retrieved a widget from the store.

    :param name: widget name
    :type name: str
    :returns: object
    """
    return _widgets.get(name)


def remove_widget(name):
    """
    Remove widget with name.

    :param name: widget name
    :type name: str
    :returns: removed widget
    """
    return _widgets.pop(name)


def add_widgets(widgets):
    """
    Add widgets from dict.

    Raises TypeError if supplied argument is not a dictionary.

    :param widgets: widgets dictionary
    :type widgets: dict
    :returns: None
    :raises: TypeError
    """
    if widgets is None:
        return
    if isinstance(widgets, dict):
        for name, widget in list(widgets.items()):
            add_widget(name, widget)
    else:
        raise TypeError("argmument has to be a dict")


class WidgetWithNameExistsError(Exception):
    """
    Exception that gets raised if it is attempted to overwrite a
    widget reference that already exists.
    """
    pass
