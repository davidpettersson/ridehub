import re

from django import template
from django.utils.html import format_html

from web import design

register = template.Library()

ICON_NAME = re.compile(r'^[a-z0-9-]+$')

SVG = '<svg class="{}" aria-hidden="true"><use href="#i-{}"/></svg>'


@register.simple_tag
def icon(name, extra_class=''):
    if not name or not ICON_NAME.match(name):
        return ''
    return format_html(SVG, f'ico {extra_class}'.strip(), name)


@register.simple_tag
def weather_icon(summary):
    if summary is None:
        return ''
    glyph = design.weather_glyph(summary.condition_primary, summary.condition_warning)
    classes = 'ico ico-wx ico-wx--risk' if summary.condition_warning else 'ico ico-wx'
    return format_html(SVG, classes, glyph)


@register.simple_tag
def condition_icon(condition):
    return format_html(SVG, 'ico ico-wx', design.weather_glyph(condition))


@register.filter
def weather_words(summary):
    if summary is None:
        return ''
    return design.weather_words(summary)


@register.inclusion_tag('web/events/_program_pill.html')
def program_pill(program, on_date=None):
    if program is None or design.program_repeats_day(program, on_date):
        return {'program': None}
    return {'program': program, 'palette': design.program_palette(program)}


@register.inclusion_tag('web/events/_event_meta.html')
def event_meta(event, density='compact', forecast_state=None, omit=''):
    omitted = {key.strip() for key in omit.split(',') if key.strip()}
    return {
        'event': event,
        'density': density,
        'items': design.event_meta_items(event, forecast_state=forecast_state, omit=omitted),
    }


@register.inclusion_tag('web/events/_event_stats.html')
def event_stats(event):
    return {'event': event, 'items': design.event_stats_items(event)}
