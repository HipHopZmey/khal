#!/usr/bin/env python2
# coding: utf-8
# vim: set ts=4 sw=4 expandtab sts=4:
# Copyright (c) 2011-2014 Christian Geier & contributors
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
import logging
import os
import re
import signal
import sys

import pytz
import xdg.BaseDirectory

from khal import version

__productname__ = 'khal'
__version__ = version.__version__
__author__ = 'Christian Geier'
__copyright__ = 'Copyright 2013-2014 Christian Geier & contributors'
__author_email__ = 'khal@lostpackets.de'
__description__ = 'A CalDAV based calendar'
__license__ = 'Expat/MIT, see COPYING'
__homepage__ = 'http://lostpackets.de/khal/'


def capture_user_interruption():
    """
    Tries to hide to the user the ugly python backtraces generated by
    pressing Ctrl-C.
    """
    signal.signal(signal.SIGINT, lambda x, y: sys.exit(0))


class Namespace(dict):
    """The khal configuration holder.

    Mostly taken from pycarddav.

    This holder is a dict subclass that exposes its items as attributes.
    Inspired by NameSpace from argparse, Configuration is a simple
    object providing equality by attribute names and values, and a
    representation.

    Warning: Namespace instances do not have direct access to the dict
    methods. But since it is a dict object, it is possible to call
    these methods the following way: dict.get(ns, 'key')

    See http://code.activestate.com/recipes/577887-a-simple-namespace-class/
    """
    def __init__(self, obj=None):
        dict.__init__(self, obj if obj else {})

    def __dir__(self):
        return list(self)

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__, dict.__repr__(self))

    def __getattribute__(self, name):
        try:
            return self[name]
        except KeyError:
            msg = "'%s' object has no attribute '%s'"
            raise AttributeError(msg % (type(self).__name__, name))

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]


class Section(object):

    READERS = {bool: ConfigParser.SafeConfigParser.getboolean,
               float: ConfigParser.SafeConfigParser.getfloat,
               int: ConfigParser.SafeConfigParser.getint,
               str: ConfigParser.SafeConfigParser.get}

    def __init__(self, parser, group):
        self._parser = parser
        self._group = group
        self._schema = None
        self._parsed = {}

    def matches(self, name):
        return self._group == name.lower()

    def is_collection(self):
        return False

    def parse(self, section):
        if self._schema is None:
            return None

        for option, default, filter_ in self._schema:
            try:
                if filter_ is None:
                    reader = ConfigParser.SafeConfigParser.get
                    filter_ = lambda x: x
                else:
                    reader = Section.READERS[type(default)]
                try:  # TODO ugly, there probably is a much better way
                    self._parsed[option] = filter_(reader(self._parser,
                                                          section,
                                                          option))
                except ConfigParser.InterpolationSyntaxError:
                    self._parsed[option] = filter_(reader(self._parser,
                                                          section,
                                                          option,
                                                          raw=True))

                # Remove option once handled (see the check function).
                self._parser.remove_option(section, option)
            except ConfigParser.Error:
                self._parsed[option] = default

        return Namespace(self._parsed)

    @property
    def group(self):
        return self._group

    def _parse_bool_string(self, value):
        """if value is either 'True' or 'False' it returns that value as a bool,
        otherwise it returns the value"""
        value = value.strip().lower()
        if value == 'true':
            return True
        elif value == 'false':
            return False
        else:
            return os.path.expanduser(value)

    def _parse_time_zone(self, value):
        """returns pytz timezone"""
        return pytz.timezone(value)


class CalendarSection(Section):
    def __init__(self, parser):
        Section.__init__(self, parser, 'calendars')
        self._schema = [
            ('path', '', os.path.expanduser),
            ('readonly', False, None),
            ('color', '', None)
        ]

    def is_collection(self):
        return True

    def matches(self, name):
        match = re.match('calendar (?P<name>.*)', name, re.I)
        if match:
            self._parsed['name'] = match.group('name')
        return match is not None


class SQLiteSection(Section):
    def __init__(self, parser):
        Section.__init__(self, parser, 'sqlite')
        self._schema = [
            ('path', ConfigurationParser.DEFAULT_DB_PATH, os.path.expanduser),
        ]


class DefaultSection(Section):
    def __init__(self, parser):
        Section.__init__(self, parser, 'default')
        self._schema = [
            ('debug', False, None),
            ('local_timezone', '', self._parse_time_zone),
            ('default_timezone', '', self._parse_time_zone),
            ('timeformat', '', None),
            ('dateformat', '', None),
            ('longdateformat', '', None),
            ('datetimeformat', '', None),
            ('longdatetimeformat', '', None),
            ('encoding', 'utf-8', None),
            ('unicode_symbols', 'True', self._parse_bool_string),
            ('firstweekday', 0, lambda x: x)
        ]


class ConfigurationParser(object):
    """A Configuration setup tool.

    This object takes care of command line parsing as well as
    configuration loading. It also prepares logging and updates its
    output level using the debug flag read from the command-line or
    the configuration file.
    """
    DEFAULT_DB_PATH = xdg.BaseDirectory.save_data_path('khal') + '/khal.db'
    DEFAULT_PATH = "khal"
    DEFAULT_FILE = "khal.conf"

    def __init__(self, desc, check_calendars=True):
        # Set the configuration current schema.
        self._sections = [CalendarSection, SQLiteSection, DefaultSection]

        # Build parsers and set common options.
        self._check_calendars = check_calendars
        self._conf_parser = ConfigParser.SafeConfigParser()
        self._arg_parser = argparse.ArgumentParser(description=desc)

        self._arg_parser.add_argument(
            "-v", "--version", action='version', version=__version__)
        self._arg_parser.add_argument(
            "-c", "--config", action="store", dest="filename",
            default=self._get_default_configuration_file(), metavar="FILE",
            help="an alternate configuration file")
        self._arg_parser.add_argument(
            "--debug", action="store_true", dest="debug",
            help="enables debugging")
        self._arg_parser.add_argument(
            "-a", "--calendar", action="append", dest="active_calendars",
            metavar="NAME",
            help="use only calendar NAME (can be used more than once)")
        self._arg_parser.add_argument(
            '--sync', action='store_true', dest='update',
            help="update the database")
        self._arg_parser.add_argument(
            "-i", "--import", metavar="FILE",
            type=argparse.FileType("r"), dest="importing",
            help="import ics from FILE into the first specified calendar")
        self._arg_parser.add_argument(
            '--new', nargs='+',
            help="create a new event")
        self._arg_parser.add_argument('--list-calendars', action='store_true',
                                      help=argparse.SUPPRESS)

    def parse(self):
        """Start parsing.

        Once the commandline parser is eventually configured with specific
        options, this function must be called to start parsing. It first
        parses the command line, and then the configuration file.

        If parsing is successful, the function check is then called.
        When check is a success, the Configuration instance is
        returned. On any error, None is returned.
        """
        args = self._read_command_line()

        # Prepare the logger with the level read from command line.
        logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

        if not args.filename:
            logging.error('Could not find configuration file')
            return None
        try:
            if not self._conf_parser.read(os.path.expanduser(args.filename)):
                logging.error('Cannot read %s', args.filename)
                return None
            else:
                logging.debug('Using configuration from %s', args.filename)
        except ConfigParser.Error as error:
            logging.error("Could not parse %s: %s", args.filename, error)
            return None

        conf = self._read_configuration(args)

        # Update the logger using the definitive output level.
        logging.getLogger().setLevel(logging.DEBUG if conf.debug else logging.INFO)

        return conf if self.check(conf) else None

    def check(self, ns):
        """Check the configuration before returning it from parsing.

        This default implementation warns the user of the remaining
        options found in the configuration file. It then checks the
        validity of the common configuration values. It returns True
        on success, False otherwise.

        This function can be overriden to augment the checks or the
        configuration tweaks achieved before the parsing function
        returns.
        """
        result = True

        for section in self._conf_parser.sections():
            for option in self._conf_parser.options(section):
                logging.debug("Ignoring %s:%s in configuration file", section, option)

        #if ns.syncrun:  # TODO when are we doing this?
        if self.check_property(ns, 'calendars'):
            for calendar in ns.calendars:
                result &= self.check_calendar(calendar)
        else:
            logging.error("No calendar found")
            result = False

        # create the db dir if it doesn't exist
        dbdir = ns.sqlite.path.rsplit('/', 1)[0]
        if not os.path.isdir(dbdir):
            try:
                logging.debug('trying to create the directory for the db')
                os.makedirs(dbdir, mode=0o770)
                logging.debug('success')
            except OSError as error:
                logging.fatal('failed to create {0}: {1}'.format(dbdir, error))
                return False

        calendars = [calendar.name for calendar in ns.calendars]

        if ns.active_calendars:
            for name in set(ns.active_calendars):
                if not name in [a.name for a in ns.calendars]:
                    logging.warn('Unknown calendar %s', name)
                    ns.active_calendars.remove(name)
            if len(ns.active_calendars) == 0:
                logging.error('No valid calendar selected')
                result = False
        else:
            ns.active_calendars = calendars

        ns.active_calendars = set(ns.active_calendars)
        # converting conf.calendars to a dict (where calendar.names are the keys)
        out = dict()
        for one in ns.calendars:
            out[one.name] = one
        ns.calendars = out

        return result

    def check_calendar(self, ns):
        if not self.check_property(ns, 'path',
                                   'Calendar {0}:path'.format(ns.name)):
            return False
        else:
            return True

    def check_property(self, ns, property_, display_name=None):
        names = property_.split('.')
        obj = ns
        try:
            for name in names:
                obj = dict.get(obj, name)
            if not obj:
                raise AttributeError()
        except AttributeError:
            logging.error('Mandatory option %s is missing',
                          display_name if display_name else property_)
            return False

        return True

    def dump(self, conf, intro='Using configuration:', tab=0):
        """Dump the loaded configuration using the logging framework.

        The values displayed here are the exact values which are seen by
        the program, and not the raw values as they are read in the
        configuration file.
        """
        if isinstance(conf, (Namespace, dict, list)):
            logging.debug('{0}{1}:'.format('\t' * tab, intro))

        if isinstance(conf, (Namespace, dict)):
            for name, value in sorted(dict.copy(conf).items()):
                self.dump(value, name, tab=tab + 1)
        elif isinstance(conf, list):
            for o in conf:
                self.dump(o, '\t'*tab + intro + ':', tab + 1)
        elif intro != 'password':
            logging.debug('{0}{1}: {2}'.format('\t'*tab, intro, conf))
        else:  # should be only the password case
            return

    def _read_command_line(self):
        items = {}
        for key, value in vars(self._arg_parser.parse_args()).items():
            if '__' in key:
                section, option = key.split('__')
                items.setdefault(section, Namespace({}))[option] = value
            else:
                items[key] = value
        return Namespace(items)

    def _read_configuration(self, overrides):
        """Build the configuration holder.

        First, data declared in the configuration schema are extracted
        from the configuration file, with type checking and possibly
        through a filter. Then these data are completed or overriden
        using the values read from the command line.
        """
        items = {}
        try:
            if self._conf_parser.getboolean('default', 'debug'):
                overrides['debug'] = True
        except ValueError:
            pass

        for section in self._conf_parser.sections():
            parser = self._get_section_parser(section)
            if not parser is None:
                values = parser.parse(section)
                if parser.is_collection():
                    if parser.group not in items:
                        items[parser.group] = []
                    items[parser.group].append(values)
                else:
                    items[parser.group] = values

        for key in dir(overrides):
            items[key] = Namespace.get(overrides, key)

        return Namespace(items)

    def _get_section_parser(self, section):
        for cls in self._sections:
            parser = cls(self._conf_parser)
            if parser.matches(section):
                return parser
        return None

    def _get_default_configuration_file(self):
        """Return the configuration filename.

        This function builds the list of paths known by khal and
        then return the first one which exists. The first paths
        searched are the ones described in the XDG Base Directory
        Standard. Each one of this path ends with
        DEFAULT_PATH/DEFAULT_FILE.

        On failure, the path DEFAULT_PATH/DEFAULT_FILE, prefixed with
        a dot, is searched in the home user directory. Ultimately,
        DEFAULT_FILE is searched in the current directory.
        """
        paths = []

        resource = os.path.join(
            ConfigurationParser.DEFAULT_PATH, ConfigurationParser.DEFAULT_FILE)
        paths.extend([os.path.join(path, resource)
                      for path in xdg.BaseDirectory.xdg_config_dirs])

        paths.append(os.path.expanduser(os.path.join('~', '.' + resource)))
        paths.append(os.path.expanduser(ConfigurationParser.DEFAULT_FILE))

        for path in paths:
            if os.path.exists(path):
                return path

        return None
