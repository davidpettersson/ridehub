from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from backoffice.models import Forecast

Condition = Forecast.Condition

SEVERITY_ORDER = list(Condition)
NOTABLE_CONDITIONS = {Condition.RAIN, Condition.SNOW, Condition.THUNDER}
CONDITION_WARNING_LABELS = {
    Condition.RAIN: 'rain',
    Condition.SNOW: 'snow',
    Condition.THUNDER: 'thunderstorms',
}

AQHI_CATEGORY_ORDER = ['low', 'moderate', 'high', 'very high']
AQHI_WARNING_CATEGORIES = {'high', 'very high'}

TEMPERATURE_COLLAPSE_SPAN = 2


@dataclass(frozen=True)
class HourlyReading:
    time: datetime
    condition: Condition
    temperature: int
    aqhi: int
    aqhi_display: str
    aqhi_category: str


@dataclass(frozen=True)
class ForecastSummary:
    condition_primary: Condition
    condition_warning: Condition | None
    condition_warning_label: str | None
    temperature_display: str
    temperature_aria_label: str
    aqhi_category: str
    aqhi_warning_category: str | None
    aria_label: str
    hourly: list[HourlyReading]


def summarize(forecast: Forecast) -> ForecastSummary:
    hourly = [_reading(entry) for entry in forecast.hourly]

    condition_primary = _prevalent_condition(hourly)
    condition_warning = _condition_warning(hourly, condition_primary)
    condition_warning_label = CONDITION_WARNING_LABELS.get(condition_warning) if condition_warning else None

    temperature_display, temperature_aria_label = _temperature(hourly)

    aqhi_category = _prevalent_aqhi_category(hourly)
    aqhi_warning_category = _aqhi_warning(hourly, aqhi_category)

    aria_label = _aria_label(
        condition_primary, condition_warning_label,
        temperature_aria_label,
        aqhi_category, aqhi_warning_category,
    )

    return ForecastSummary(
        condition_primary=condition_primary,
        condition_warning=condition_warning,
        condition_warning_label=condition_warning_label,
        temperature_display=temperature_display,
        temperature_aria_label=temperature_aria_label,
        aqhi_category=aqhi_category,
        aqhi_warning_category=aqhi_warning_category,
        aria_label=aria_label,
        hourly=hourly,
    )


def _reading(entry: dict) -> HourlyReading:
    aqhi = entry['aqhi']
    return HourlyReading(
        time=datetime.fromisoformat(entry['time']),
        condition=Condition(entry['condition']),
        temperature=entry['temperature'],
        aqhi=aqhi,
        aqhi_display=Forecast.format_aqhi(aqhi),
        aqhi_category=Forecast.aqhi_category_for(aqhi),
    )


def _prevalent_condition(hourly: list[HourlyReading]) -> Condition:
    counts = Counter(reading.condition for reading in hourly)
    return max(counts, key=lambda condition: (counts[condition], SEVERITY_ORDER.index(condition)))


def _condition_warning(hourly: list[HourlyReading], prevalent: Condition) -> Condition | None:
    prevalent_severity = SEVERITY_ORDER.index(prevalent)
    candidates = [
        reading.condition for reading in hourly
        if reading.condition in NOTABLE_CONDITIONS and SEVERITY_ORDER.index(reading.condition) > prevalent_severity
    ]
    if not candidates:
        return None
    return max(candidates, key=SEVERITY_ORDER.index)


def _temperature(hourly: list[HourlyReading]) -> tuple[str, str]:
    temperatures = [reading.temperature for reading in hourly]
    low, high = min(temperatures), max(temperatures)
    if high - low <= TEMPERATURE_COLLAPSE_SPAN:
        midpoint = (low + high + 1) // 2
        return str(midpoint), f'{midpoint} degrees Celsius'
    return f'{low}–{high}', f'{low} to {high} degrees Celsius'


def _prevalent_aqhi_category(hourly: list[HourlyReading]) -> str:
    counts = Counter(reading.aqhi_category for reading in hourly)
    return max(counts, key=lambda category: (counts[category], AQHI_CATEGORY_ORDER.index(category)))


def _aqhi_warning(hourly: list[HourlyReading], prevalent_category: str) -> str | None:
    worst = max((reading.aqhi_category for reading in hourly), key=AQHI_CATEGORY_ORDER.index)
    if worst in AQHI_WARNING_CATEGORIES and AQHI_CATEGORY_ORDER.index(worst) > AQHI_CATEGORY_ORDER.index(prevalent_category):
        return worst
    return None


def _aria_label(
    condition_primary: Condition,
    condition_warning_label: str | None,
    temperature_aria_label: str,
    aqhi_category: str,
    aqhi_warning_category: str | None,
) -> str:
    condition_text = Forecast.CONDITION_ARIA_LABELS[condition_primary]
    if condition_warning_label:
        condition_text += f', {condition_warning_label} possible'
    aqhi_text = f'air quality {aqhi_category}'
    if aqhi_warning_category:
        aqhi_text += f', spike to {aqhi_warning_category}'
    return f'Weather: {condition_text}, {temperature_aria_label}, {aqhi_text}'
