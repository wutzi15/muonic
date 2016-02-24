"""
Utility functions
"""
import os

from muonic import DATA_PATH


def setup_data_directory(directory=DATA_PATH):
    """
    Tries to create the data directory if it is not present. Also tries to
    set the appropriate permissions if it is not writeable.

    :param directory: the directory to set up
    :type directory: str
    :returns: None
    """
    if not os.path.isdir(directory):
        os.mkdir(directory, 0755)
    elif not os.access(directory, os.W_OK):
        os.chmod(directory, 0755)
