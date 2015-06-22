# vim: set fileencoding=utf-8 :

from datetime import datetime, date, timedelta
import textwrap

import pytest
import pytz

from khal.khalendar.event import Event, AllDayEvent, LocalizedEvent, \
    FloatingEvent

from .aux import normalize_component, _get_text


BERLIN = pytz.timezone('Europe/Berlin')
# the lucky people in Bogota don't know the pain that is DST
BOGOTA = pytz.timezone('America/Bogota')

LOCALE = {
    'default_timezone': BERLIN,
    'local_timezone': BERLIN,
    'dateformat': '%d.%m.',
    'timeformat': '%H:%M',
    'longdateformat': '%d.%m.%Y',
    'datetimeformat': '%d.%m. %H:%M',
    'longdatetimeformat': '%d.%m.%Y %H:%M',
    'unicode_symbols': True,
}
EVENT_KWARGS = {'href': None, 'etag': None,
                'calendar': 'foobar', 'locale': LOCALE}


def test_raw_dt():
    event_dt = _get_text('event_dt_simple')
    event = Event.fromString(event_dt, **EVENT_KWARGS)
    assert normalize_component(event.raw) == normalize_component(_get_text('event_dt_simple_inkl_vtimezone'))
    assert event.relative_to(date(2014, 4, 9)) == u'09:30-10:30: An Event'

    event = Event.fromString(event_dt, **EVENT_KWARGS)
    assert event.relative_to(date(2014, 4, 9)) == u'09:30-10:30: An Event'
    assert event.event_description == u'09:30-10:30 09.04.2014: An Event'
    assert event.recurring is False


def test_raw_d():
    event_d = _get_text('event_d')
    event = Event.fromString(event_d, **EVENT_KWARGS)
    assert event.raw.split('\r\n') == _get_text('cal_d').split('\n')
    assert event.relative_to(date(2014, 4, 9)) == u'An Event'
    assert event.event_description == u'09.04.2014: An Event'


def test_transform_event():
    """test if transformation between different event types works"""
    event_d = _get_text('event_d')
    event = Event.fromString(event_d, **EVENT_KWARGS)
    assert isinstance(event, AllDayEvent)
    start = BERLIN.localize(datetime(2014, 4, 9, 9, 30))
    end = BERLIN.localize(datetime(2014, 4, 9, 10, 30))
    event.update_start_end(start, end)
    assert isinstance(event, LocalizedEvent)
    assert event.event_description == u'09:30-10:30 09.04.2014: An Event'
    analog_event = Event.fromString(_get_text('event_dt_simple'), **EVENT_KWARGS)
    assert normalize_component(event.raw) == normalize_component(analog_event.raw)


def test_dt_two_tz():
    event_dt_two_tz = _get_text('event_dt_two_tz')
    cal_dt_two_tz = _get_text('cal_dt_two_tz')

    event = Event.fromString(event_dt_two_tz, **EVENT_KWARGS)
    assert normalize_component(cal_dt_two_tz) == normalize_component(event.raw)

    # local (Berlin) time!
    assert event.relative_to(date(2014, 4, 9)) == u'09:30-16:30: An Event'
    assert event.event_description == u'09:30-16:30 09.04.2014: An Event'


def test_event_dt_duration():
    """event has no end, but duration"""
    event_dt_duration = _get_text('event_dt_duration')
    event = Event.fromString(event_dt_duration, **EVENT_KWARGS)
    assert event.relative_to(date(2014, 4, 9)) == u'09:30-10:30: An Event'
    assert event.end == BERLIN.localize(datetime(2014, 4, 9, 10, 30))
    assert event.event_description == u'09:30-10:30 09.04.2014: An Event'


def test_event_dt_no_tz():
    """start and end time of no timezone"""
    event_dt_no_tz = _get_text('event_dt_no_tz')
    event = Event.fromString(event_dt_no_tz, **EVENT_KWARGS)
    assert event.relative_to(date(2014, 4, 9)) == u'09:30-10:30: An Event'
    assert event.event_description == u'09:30-10:30 09.04.2014: An Event'


def test_event_rr():
    event_dt_rr = _get_text('event_dt_rr')
    event = Event.fromString(event_dt_rr, **EVENT_KWARGS)
    assert event.recurring is True
    desc = u'09:30-10:30: An Event ⟳'
    assert event.relative_to(date(2014, 4, 9)) == desc
    assert event.event_description == u'09:30-10:30 09.04.2014: An Event\nRepeat: FREQ=DAILY;COUNT=10'

    event_d_rr = _get_text('event_d_rr')
    event = Event.fromString(event_d_rr, **EVENT_KWARGS)
    assert event.recurring is True
    desc = u'Another Event ⟳'
    assert event.relative_to(date(2014, 4, 9)) == desc
    assert event.event_description == u'09.04.2014: Another Event\nRepeat: FREQ=DAILY;COUNT=10'


def test_event_rd():
    event_dt_rd = _get_text('event_dt_rd')
    event = Event.fromString(event_dt_rd, **EVENT_KWARGS)
    assert event.recurring is True


def test_event_d_long():
    event_d_long = _get_text('event_d_long')
    event = Event.fromString(event_d_long, **EVENT_KWARGS)
    with pytest.raises(ValueError):
        event.relative_to(date(2014, 4, 8))
    assert event.relative_to(date(2014, 4, 9)) == u'↦ Another Event'
    assert event.relative_to(date(2014, 4, 10)) == u'↔ Another Event'
    assert event.relative_to(date(2014, 4, 11)) == u'⇥ Another Event'
    with pytest.raises(ValueError):
        event.relative_to(date(2014, 4, 12))
    assert event.event_description == u'09.04. - 11.04.2014: Another Event'


def test_event_dt_long():
    event_dt_long = _get_text('event_dt_long')
    event = Event.fromString(event_dt_long, **EVENT_KWARGS)
    with pytest.raises(ValueError):
        event.relative_to(date(2014, 4, 8))
    assert event.relative_to(date(2014, 4, 9)) == u'09:30→ : An Event'
    # FIXME ugly! replace with one arrow
    assert event.relative_to(date(2014, 4, 10)) == u'→ → : An Event'
    assert event.relative_to(date(2014, 4, 12)) == u'→ 10:30: An Event'
    with pytest.raises(ValueError):
        event.relative_to(date(2014, 4, 13))
    assert event.event_description == u'09.04.2014 09:30 - 12.04.2014 10:30: An Event'


def test_event_no_dst():
    """test the creation of a corect VTIMEZONE for timezones with no dst"""
    BOGOTA_LOCALE = LOCALE.copy()
    BOGOTA_LOCALE['local_timezone'] = BOGOTA
    BOGOTA_LOCALE['default_timezone'] = BOGOTA
    event_no_dst = _get_text('event_no_dst')
    cal_no_dst = _get_text('cal_no_dst')
    event = Event.fromString(event_no_dst, calendar='foobar', locale=BOGOTA_LOCALE,
                             href=None, etag=None)
    assert normalize_component(event.raw) == normalize_component(cal_no_dst)
    assert event.event_description == u'09:30-10:30 09.04.2014: An Event'


def test_dtend_equals_dtstart():
    event = Event.fromString(_get_text('event_d_same_start_end'),
                             calendar='foobar', locale=LOCALE, href=None,
                             etag=None)
    assert event.end == event.start
