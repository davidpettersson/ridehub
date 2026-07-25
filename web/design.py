import re

from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as format_datetime

from backoffice.models import Event, Forecast

Condition = Forecast.Condition

PROGRAM_PALETTES = {
    'sunday': 'sunday',
    'sundayride': 'sunday',
    'sundayrides': 'sunday',
    'road': 'road',
    'roadride': 'road',
    'roadrides': 'road',
    'gravel': 'gravel',
    'gravelride': 'gravel',
    'gravelrides': 'gravel',
    'women': 'womens',
    'womens': 'womens',
    'womensride': 'womens',
    'womensrides': 'womens',
    'opentimetrial': 'time-trial',
    'timetrial': 'time-trial',
    'training': 'training',
    'outoftown': 'out-of-town',
}

NEUTRAL_PALETTE = 'neutral'

WEATHER_GLYPHS = {
    Condition.SUN: 'sun',
    Condition.CLOUD: 'cloud',
    Condition.RAIN: 'cloud-rain',
    Condition.SNOW: 'cloud-snow',
    Condition.THUNDER: 'cloud-bolt',
}

WEATHER_COMPOSITE_GLYPHS = {
    (Condition.SUN, Condition.RAIN): 'sun-rain',
    (Condition.SUN, Condition.SNOW): 'sun-snow',
    (Condition.SUN, Condition.THUNDER): 'sun-bolt',
    (Condition.CLOUD, Condition.RAIN): 'cloud-rain',
    (Condition.CLOUD, Condition.SNOW): 'cloud-snow',
    (Condition.CLOUD, Condition.THUNDER): 'cloud-bolt',
    (Condition.RAIN, Condition.SNOW): 'cloud-snow',
    (Condition.RAIN, Condition.THUNDER): 'cloud-bolt',
    (Condition.SNOW, Condition.THUNDER): 'cloud-bolt',
}

FALLBACK_WEATHER_GLYPH = 'cloud'

FULL_DENSITY_KEYS = ('location', 'weather', 'registrations')

CONDITION_WORDS = {
    Condition.SUN: 'sun',
    Condition.CLOUD: 'cloud',
    Condition.RAIN: 'rain',
    Condition.SNOW: 'snow',
    Condition.THUNDER: 'thunderstorms',
}

CONDITION_RISK_WORDS = {
    Condition.RAIN: 'rain',
    Condition.SNOW: 'snow',
    Condition.THUNDER: 'storm',
}


def normalize_name(name: str | None) -> str:
    return re.sub(r'[^a-z0-9]', '', (name or '').lower())


def program_palette(program) -> str:
    return PROGRAM_PALETTES.get(normalize_name(getattr(program, 'name', '')), NEUTRAL_PALETTE)


def weather_glyph(condition_primary, condition_warning=None) -> str:
    if condition_warning is None:
        return WEATHER_GLYPHS.get(condition_primary, FALLBACK_WEATHER_GLYPH)
    return WEATHER_COMPOSITE_GLYPHS.get(
        (condition_primary, condition_warning),
        WEATHER_GLYPHS.get(condition_warning, FALLBACK_WEATHER_GLYPH),
    )


def weather_headline(summary) -> str:
    words = CONDITION_WORDS.get(summary.condition_primary, '')
    headline = f'{summary.temperature_display}°, {words}'
    risk = CONDITION_RISK_WORDS.get(summary.condition_warning)
    if risk:
        return f'{headline} with {risk} risk'
    return headline


def weather_detail(summary) -> str:
    if not summary.condition_warning_label:
        return ''
    detail = summary.condition_warning_label.capitalize() + ' possible'
    onset = _warning_onset(summary)
    if onset:
        return f'{detail} after {onset}'
    return detail


def event_meta_items(event, forecast_state=None, omit=(), density='compact') -> list[dict]:
    candidates = [
        _location_item(event),
        _weather_item(forecast_state),
        _registrations_item(event),
        _distance_item(event),
        _time_item(event),
    ]
    items = [item for item in candidates if item and item['key'] not in omit]
    if density == 'full':
        return [item for item in items if item['key'] in FULL_DENSITY_KEYS]
    return items


def event_stats_items(event) -> list[dict]:
    candidates = [
        _rides_item(event),
        _distance_item(event),
    ]
    return [item for item in candidates if item]


def event_time_text(event) -> str:
    item = _time_item(event)
    return item['text'] if item else ''


def _location_item(event) -> dict | None:
    if not event.location and not event.location_url:
        return None
    return {
        'key': 'location',
        'icon': 'monitor' if event.virtual else 'pin',
        'text': event.location or 'See location',
        'sub': 'Open in Maps' if event.location_url else '',
        'url': event.location_url or '',
        'external': True,
        'truncates': True,
    }


def _weather_item(forecast_state) -> dict | None:
    if forecast_state is None or not forecast_state.possible:
        return None
    return {
        'key': 'weather',
        'forecast': forecast_state.forecast,
        'pending': forecast_state.pending,
    }


def _distance_text(event) -> str:
    distance_range = event.distance_range
    if not distance_range:
        return ''
    low, high = distance_range
    return f'{low} km' if low == high else f'{low}–{high} km'


def _distance_item(event) -> dict | None:
    distance = _distance_text(event)
    if not distance:
        return None
    return {'key': 'distance', 'icon': 'route', 'text': distance}


def _time_item(event) -> dict | None:
    if not event.starts_at:
        return None

    starts_at = timezone.localtime(event.starts_at)
    ends_at = timezone.localtime(event.ends_at) if event.ends_at else None
    multi_day = bool(ends_at) and ends_at.date() != starts_at.date()

    if event.all_day:
        span = f'{format_datetime(starts_at, "M j")} – {format_datetime(ends_at, "M j")}' if multi_day else ''
        text = f'{span} · All day' if span else 'All day'
        return {'key': 'time', 'icon': 'clock', 'text': text}

    end_format = 'M j, g:i A' if multi_day else 'g:i A'
    text = format_datetime(starts_at, 'g:i A')
    if ends_at and ends_at != starts_at:
        text = f'{text} – {format_datetime(ends_at, end_format)}'
    return {'key': 'time', 'icon': 'clock', 'text': text}


def _warning_onset(summary) -> str:
    for reading in summary.hourly:
        if reading.condition == summary.condition_warning:
            return format_datetime(reading.time, 'g A')
    return ''


def _rides_item(event) -> dict | None:
    if not event.has_rides:
        return None
    count = event.ride_count
    return {'key': 'rides', 'icon': 'bike', 'text': f'{count} ride{pluralize(count)}'}


def _registrations_item(event) -> dict | None:
    if event.external_registration_url or event.state == Event.STATE_ANNOUNCED:
        return None
    if event.registration_limit == 0:
        return None

    count = event.registration_count
    limit = event.registration_limit

    if count == 0:
        if not event.registration_open:
            return None
        return {
            'key': 'registrations',
            'icon': 'users',
            'text': 'Be the first to register',
            'sub': _registration_summary(event),
            'invitation': True,
            'full': False,
        }

    text = f'{count} registered' if limit is None else f'{count}/{limit} registered'
    return {
        'key': 'registrations',
        'icon': 'users',
        'text': text,
        'sub': _registration_summary(event),
        'url': reverse('riders_list', args=[event.id]),
        'invitation': False,
        'full': limit is not None and count >= limit,
    }


def _registration_summary(event) -> str:
    parts = []

    remaining = event.capacity_remaining
    if remaining:
        parts.append(f'{remaining} spot{pluralize(remaining)} left')

    if event.registration_open:
        if event.registration_closes_at:
            closes_at = timezone.localtime(event.registration_closes_at)
            parts.append(f'Closes {format_datetime(closes_at, "M j, g:i A")}')
    else:
        parts.append('Registration closed')

    return ' · '.join(parts)
