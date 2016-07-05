"""
Utility functions
"""
from __future__ import print_function
import os
import shutil

from muonic import DATA_PATH

_data_path = DATA_PATH


def setup_data_directory(directory=DATA_PATH):
    """
    Tries to create the data directory if it is not present. Also tries to
    set the appropriate permissions if it is not writeable.

    :param directory: the directory to set up
    :type directory: str
    :returns: None
    """
    if not os.path.isdir(directory):
        os.makedirs(directory, 0o755)
    elif not os.access(directory, os.W_OK):
        os.chmod(directory, 0o755)


def set_data_directory(directory):
    """
    Sets the data directory

    :param directory: the data directory
    :type directory: str
    :returns: None
    """
    global _data_path

    _data_path = directory


def get_data_directory():
    """
    Get the data directory. Acts as a proxy for custom data
    directories later on.

    :returns: str
    """
    global _data_path

    return _data_path


def get_muonic_filename(start_date, measurement_id, suffix):
    """
    Get a filename in the right format. 'measurement_id' may be a single char
    identifying the measurement type. 'suffix' may be the initials of the
    current user.

    :param start_date: the start date of the measurement
    :type start_date: date object
    :param measurement_id: the identifier of the measurement
    :type measurement_id: str
    :param suffix: the suffix
    :type suffix: str
    :returns: str
    """
    return os.path.join(get_data_directory(), "%s_%s_HOURS_%s" %
                        (start_date.strftime('%Y-%m-%d_%H-%M-%S'),
                         measurement_id,
                         suffix))


def rename_muonic_file(duration, file_path):
    """
    Replaces the placeholder 'HOURS' in filename by the elapsed amount of
    hours since measurement started.

    Raises OSError if the file_path does not contain a filename.

    :param duration: the duration of the measurement
    :type duration: date object
    :param file_path: the file path
    :type file_path: str
    :raises: OSError
    :returns: bool
    """
    hours = get_hours_from_duration(duration)

    path, filename = os.path.split(file_path)

    if filename == "":
        raise OSError("filename is empty")

    new_filename = filename.replace("HOURS", str(hours))

    # move file
    shutil.move(file_path, os.path.join(path, new_filename))


def get_hours_from_duration(duration):
    """
    Get the hourse from a given duration

    :param duration: the duration of the measurement
    :type duration: date object
    :returns: float
    """
    return round(duration.seconds / 3600., 2) + duration.days * 24


def format_date(date, fmt="%Y-%m-%d_%H-%M-%S"):
    """
    Format time by the provides format.

    :param date: the date
    :type: date object
    :param fmt: the date format
    :type fmt: str
    :returns: str
    """
    return date.strftime(fmt)


class WrappedFile(object):
    """
    A file wrapper which keeps track of open files.

    Raises ValueError if filename is None.

    :param filename: the filename
    :type filename: str
    :raises: ValueError
    """
    open_files = set()

    def __init__(self, filename):
        if filename is None:
            raise ValueError("filename cannot be of 'NoneType'")

        self._filename = filename
        self._file = None

    def get_filename(self):
        """
        Get the filename

        :returns: str
        """
        return self._filename

    def open(self, mode='w'):
        """
        Open file and track it.

        :param mode: the file mode
        :type mode: str
        :returns: None
        """
        self._file = open(self._filename, mode)
        WrappedFile.open_files.add(self._filename)
        return self

    @property
    def closed(self):
        """
        Returns True if the file is closed, False otherwise.

        :returns: bool
        """
        if self._file is None:
            return True
        return False

    def close(self):
        """
        Close file and un-track it.

        Raises IOError if file is not open.

        :raises: IOError
        :returns: None
        """
        if self._file is None:
            raise IOError("file '%s' is not open" % self._filename)
        self._file.close()
        self._file = None
        WrappedFile.open_files.remove(self._filename)

    def __enter__(self):
        """
        Return file on entering 'with' block

        :returns: file
        """
        return self._file

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Close file on leaving 'with' block.

        Exit the runtime context related to this object. The parameters
        describe the exception that caused the context to be exited. If
        the context was exited without an exception, all three arguments
        will be None.

        :param exc_type: type of the Exception that caused the
        context to be exited
        :param exc_value: value of the Exception
        :param traceback: traceback, if any
        :returns: None
        """
        self.close()

    def __getattr__(self, attr):
        """
        Proxy all other attributes of file.

        Raises IOError if file is not open.

        :param attr: attribute name
        :type attr: str
        :raises: IOError
        :returns: mixed
        """
        if self._file is None:
            raise IOError("file '%s' is not open" % self._filename)
        return getattr(self._file, attr)

    def __repr__(self):
        """
        Representation

        :returns: str
        """
        return self._filename

    @staticmethod
    def get_open_files():
        """
        Get all open files.

        :returns: set of str
        """
        return WrappedFile.open_files
