# digital_pass.py
#
# Copyright 2022 Pablo Sánchez Rodríguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re

from datetime import datetime

from gi.repository import GdkPixbuf, GObject


class DigitalPass(GObject.GObject):

    __gtype_name__ = 'DigitalPass'

    def __init__(self):
        super().__init__()
        self.__path = None

    def description(self):
        raise NotImplementedError()

    def background_color(self):
        raise NotImplementedError()

    def expiration_date(self):
        raise NotImplementedError()

    def format(self):
        return type(self).__name__.lower()

    def get_path(self):
        return self.__path

    def has_expired(self):
        expiration_date = self.expiration_date()
        return (not expiration_date.is_undefined() \
                and Date.now() > expiration_date) \
                or self.voided()

    def set_path(self, new_path: str):
        self.__path = new_path

    def voided(self):
        raise NotImplementedError()


class Barcode:

    def __init__(self, barcode_dictionary):
        self.__format = barcode_dictionary['format']
        self.__message = barcode_dictionary['message']

        self.__message_encoding = None
        if 'messageEncoding' in barcode_dictionary.keys():
            self.__message_encoding = barcode_dictionary['messageEncoding']

        self.__alt_text = None
        if 'altText' in barcode_dictionary.keys():
            self.__alt_text = barcode_dictionary['altText']

    def alternative_text(self):
        return self.__alt_text

    def format(self):
        return self.__format

    def message(self):
        return self.__message

    def message_encoding(self):
        return self.__message_encoding


class Color:

    def __init__(self, r, g, b):
        self.__r = r
        self.__g = g
        self.__b = b

    def as_tuple(self):
        return (self.__r, self.__g, self.__b)

    @classmethod
    def from_css(this_class, css_string):
        if css_string.startswith('rgb'):
            result = re.search('rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
                               css_string)

            if not result or len(result.groups()) != 3:
                raise BadColor()

            r = result.group(1)
            g = result.group(2)
            b = result.group(3)

        elif css_string.startswith('#'):
            result = re.search('\#(\S{2})(\S{2})(\S{2})(\S{2})',
                               css_string)

            if not result or len(result.groups()) != 4:
                raise BadColor()

            r = int(result.group(2), 16)
            g = int(result.group(3), 16)
            b = int(result.group(4), 16)

        else:
            raise BadColor()

        return Color(r, g, b)

    def invert(self):
        self.__r = 255 - self.__r
        self.__g = 255 - self.__g
        self.__b = 255 - self.__b


class Date:

    days_of_the_week = (_('Monday'), _('Tuesday'), _('Wednesday'),
                        _('Thursday'), _('Friday'), _('Saturday'), _('Sunday'))

    MAX = datetime(9000, 12, 31).astimezone()
    MIN = datetime(1970,  1,  1).astimezone()

    def __init__(self):
        self.__date = None

    def __eq__(self, other):

        if not self.__date or not other.__date:
            return False

        return self.__date.timestamp() == other.__date.timestamp()

    def __lt__(self, other):

        if self.__date and not other.__date:
            return True

        if not self.__date and other.__date:
            return False

        if not self.__date and not other.__date:
            return False

        return self.__date < other.__date

    def __str__(self):
        return 'Undefined' if self.is_undefined() else str(self.__date)

    def as_relative_pretty_string(self):

        if not self.__date:
            return _('Anytime')

        today = datetime.today().date()
        time_difference = self.__date.date() - today

        if time_difference.days == 0:
            return _('Today')

        if time_difference.days == 1:
            return _('Tomorrow')

        if 0 < time_difference.days < 7:
            return Date.days_of_the_week[int(self.__date.strftime('%w')) - 1]

        return self.__date.strftime('%x')

    @classmethod
    def from_iso_string(self, string):

        instance = Date()

        if not string:
            return instance

        if string.endswith('Z'):
            string = string[:-1]

        # Make sure that milliseconds is represented using 3 digits
        match = re.match('^(.+)(\d{2})(\+.+$)', string)
        if match:
            string = match.group(1) + match.group(2) + '0' + match.group(3)

        try:
            # Create the date and make sure that it is not "naive"
            date = None
            date = datetime.fromisoformat(string).astimezone()

        finally:
            instance.__date = date

        return instance

    def is_undefined(self):
        return self.__date == None

    @classmethod
    def now(self):
        instance = Date()
        instance.__date = datetime.now().astimezone()
        return instance

class Image:

    def __init__(self, image_data):
        self.__data = image_data

    def as_pixbuf(self):
        loader = GdkPixbuf.PixbufLoader()
        loader.write(self.__data)
        loader.close()
        return loader.get_pixbuf()


class PassDataExtractor:
    """
    A PassDataExtractor contains a reference to a dictionary and a set of helper
    functions to easy the process of creating a pass.
    """

    def __init__(self, dictionary):
        self._dictionary = dictionary

    def _cast_to_boolean(self, value):
        """
        Protected method that creates a boolean from a string.
        """
        return True if value.lower().startswith('true') else False

    def get(self, key, type_constructor=None):
        """
        Return an element from the dictionary using the provided key.

        If a constructor is specified, it will be used to create the instance
        that will be returned.
        """
        try:
            value = None

            if key in self._dictionary:
                value = self._dictionary[key]

            if not type_constructor and type(value) == dict:
                return PassDataExtractor(value)

            if type_constructor:
                if type(type_constructor) == bool:
                    value = self._cast_to_boolean(value)

                else:
                    value = type_constructor(value)

            return value

        except:
            return None

    def get_list(self, key, item_constructor=None, extra_arguments=None):
        """
        Return a list of elements from the dictionary using the provided key.

        If a constructor is specified, it will be used to create each of the
        items that will be appended to the list.
        """

        data_list = self.get(key)

        if not data_list:
            return []

        if not extra_arguments:
            extra_arguments = ()

        elif type(extra_arguments) != tuple:
            extra_arguments = (extra_arguments,)

        result = list()
        for item_data in data_list:
            arguments = (item_data,) + extra_arguments

            if item_constructor:
                instance = item_constructor(*arguments)
            else:
                instance = item_data

            result.append(instance)

        return result

    def keys(self):
        """
        Return the set of keys
        """
        return self._dictionary.keys()


class TimeInterval:
    def __init__(self, start_time, end_time):
        self.__start_time = start_time
        self.__end_time = end_time

    def __contains__(self, time):
        if (self.__start_time and time < self.__start_time) or \
           (self.__end_time and time > self.__end_time):
            return False

        return True

    @classmethod
    def from_iso_strings(cls, start_time, end_time):
        start_time = Date.from_iso_string(start_time) if start_time else Date.MIN
        end_time = Date.from_iso_string(end_time) if end_time else Date.MAX
        return TimeInterval(start_time, end_time)

    def end_time(self):
        return self.__end_time


class BadColor(Exception):
    pass
