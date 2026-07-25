import re
from datetime import timedelta

from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from waffle.testutils import override_flag

from backoffice.models import Event, Forecast, Program, Registration, Ride, Route, SpeedRange
from backoffice.services.forecast_service import ForecastState, YOW_LOCATION
from web import design

EMOJI = re.compile(
    '[\U0001F000-\U0001FAFF☀-➿️]'
)


def render(source, **context):
    return Template('{% load design_tags %}' + source).render(Context(context))


class DesignTagTestCase(TestCase):
    def setUp(self):
        self.program = Program.objects.create(name='Road')
        self.starts_at = timezone.localtime(
            timezone.now() + timedelta(days=1)
        ).replace(hour=9, minute=0, second=0, microsecond=0)
        self.latitude, self.longitude = YOW_LOCATION

    def create_event(self, **overrides):
        fields = {
            'program': self.program,
            'name': 'Test Event',
            'description': 'Description',
            'starts_at': self.starts_at,
            'ends_at': self.starts_at + timedelta(hours=3),
            'registration_closes_at': self.starts_at - timedelta(hours=1),
            'location': 'Andrew Haydon Park',
        }
        fields.update(overrides)
        return Event.objects.create(**fields)

    def create_forecast(self, hourly=None):
        hourly = hourly or [
            {'time': self.starts_at.strftime('%Y-%m-%dT%H:%M'), 'condition': 'cloud', 'temperature': 18, 'aqhi': 4},
            {'time': (self.starts_at + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'cloud', 'temperature': 21, 'aqhi': 4},
        ]
        return Forecast.objects.create(
            latitude=self.latitude,
            longitude=self.longitude,
            start_time=self.starts_at,
            end_time=self.starts_at + timedelta(hours=1),
            hourly=hourly,
        )

    def add_ride(self, event, distance=None):
        route = Route.objects.create(name=f'Route {distance}', distance=distance)
        return Ride.objects.create(name='Ride', event=event, route=route)


class IconTagTests(DesignTagTestCase):
    def test_icon_references_the_sprite(self):
        # Act
        html = render('{% icon "pin" %}')

        # Assert
        self.assertIn('<use href="#i-pin"/>', html)
        self.assertIn('class="ico"', html)

    def test_icon_applies_extra_class(self):
        # Act
        html = render('{% icon "clock" "ico-chevron" %}')

        # Assert
        self.assertIn('class="ico ico-chevron"', html)

    def test_icon_rejects_unsafe_name(self):
        # Act
        html = render('{% icon name %}', name='pin"/><script>alert(1)</script>')

        # Assert
        self.assertEqual(html, '')

    def test_every_referenced_icon_exists_in_the_sprite(self):
        # Arrange
        with open('web/templates/web/icons/_sprite.svg') as sprite_file:
            sprite = sprite_file.read()
        referenced = set(design.WEATHER_GLYPHS.values()) | set(design.WEATHER_COMPOSITE_GLYPHS.values())
        referenced |= {'pin', 'monitor', 'route', 'clock', 'bike', 'users', 'chevron-right'}

        # Assert
        for name in referenced:
            self.assertIn(f'id="i-{name}"', sprite)


class ProgramPillTests(DesignTagTestCase):
    def test_known_program_uses_its_palette(self):
        # Act
        html = render('{% program_pill program %}', program=self.program)

        # Assert
        self.assertIn('program-pill--road', html)
        self.assertIn('Road', html)

    def test_unknown_program_falls_back_to_neutral(self):
        # Arrange
        program = Program.objects.create(name='Brand New Thing')

        # Act
        html = render('{% program_pill program %}', program=program)

        # Assert
        self.assertIn('program-pill--neutral', html)
        self.assertIn('Brand New Thing', html)

    def test_missing_program_renders_nothing(self):
        # Act
        html = render('{% program_pill program %}', program=None)

        # Assert
        self.assertEqual(html.strip(), '')

    def test_pill_carries_no_icon(self):
        # Act
        html = render('{% program_pill program %}', program=self.program)

        # Assert
        self.assertNotIn('<svg', html)

    def test_day_named_program_is_suppressed_on_its_own_day(self):
        # Arrange
        program = Program.objects.create(name='Sunday')
        sunday = self.starts_at + timedelta(days=(6 - self.starts_at.weekday()) % 7)

        # Act
        html = render('{% program_pill program on_date=on_date %}', program=program, on_date=sunday)

        # Assert
        self.assertEqual(html.strip(), '')

    def test_day_named_program_renders_on_another_day(self):
        # Arrange
        program = Program.objects.create(name='Sunday')
        sunday = self.starts_at + timedelta(days=(6 - self.starts_at.weekday()) % 7)
        monday = sunday + timedelta(days=1)

        # Act
        html = render('{% program_pill program on_date=on_date %}', program=program, on_date=monday)

        # Assert
        self.assertIn('program-pill--sunday', html)


class EventMetaItemOrderTests(DesignTagTestCase):
    def test_items_follow_the_fixed_order(self):
        # Arrange
        event = self.create_event()
        self.add_ride(event, distance=45)

        # Act
        items = design.event_meta_items(event, forecast_state=ForecastState.ready(self.create_forecast()))

        # Assert
        self.assertEqual([item['key'] for item in items], ['location', 'weather', 'distance', 'time'])

    def test_missing_data_is_omitted(self):
        # Arrange
        event = self.create_event(location='', location_url='')

        # Act
        items = design.event_meta_items(event)

        # Assert
        self.assertEqual([item['key'] for item in items], ['time'])

    def test_omit_argument_drops_an_item(self):
        # Arrange
        event = self.create_event()
        self.add_ride(event, distance=45)

        # Act
        html = render(
            '{% event_meta event density="compact" omit="distance" %}', event=event
        )

        # Assert
        self.assertNotIn('45 km', html)
        self.assertIn('Andrew Haydon Park', html)


class EventMetaWeatherTests(DesignTagTestCase):
    def test_weather_item_omitted_when_no_forecast_state(self):
        # Arrange
        event = self.create_event()

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertNotIn('forecast-badge-', html)
        self.assertNotIn('ico-wx', html)

    def test_weather_item_omitted_when_forecast_impossible(self):
        # Arrange
        event = self.create_event()

        # Act
        html = render(
            '{% event_meta event forecast_state=state %}',
            event=event, state=ForecastState.unavailable(),
        )

        # Assert
        self.assertNotIn('forecast-badge-', html)

    def test_temperature_without_aqhi_has_no_dangling_separator(self):
        # Arrange
        event = self.create_event()
        forecast = self.create_forecast(hourly=[
            {'time': self.starts_at.strftime('%Y-%m-%dT%H:%M'), 'condition': 'sun', 'temperature': 20, 'aqhi': None},
        ])

        # Act
        html = render(
            '{% event_meta event forecast_state=state %}',
            event=event, state=ForecastState.ready(forecast),
        )

        # Assert
        self.assertIn('20&deg;', html)
        self.assertNotIn('AQHI', html)
        self.assertNotIn('&rarr;', html)

    def test_single_glyph_for_a_simple_condition(self):
        # Arrange
        event = self.create_event()

        # Act
        html = render(
            '{% event_meta event forecast_state=state %}',
            event=event, state=ForecastState.ready(self.create_forecast()),
        )

        # Assert
        self.assertEqual(html.count('<use href="#i-cloud"/>'), 1)
        self.assertEqual(html.count('ico-wx'), 1)

    def test_single_composite_glyph_for_a_compound_condition(self):
        # Arrange
        event = self.create_event()
        forecast = self.create_forecast(hourly=[
            {'time': self.starts_at.strftime('%Y-%m-%dT%H:%M'), 'condition': 'sun', 'temperature': 24, 'aqhi': 4},
            {'time': (self.starts_at + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'sun', 'temperature': 24, 'aqhi': 4},
            {'time': (self.starts_at + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'thunder', 'temperature': 24, 'aqhi': 4},
        ])

        # Act
        html = render(
            '{% event_meta event forecast_state=state %}',
            event=event, state=ForecastState.ready(forecast),
        )

        # Assert
        self.assertEqual(html.count('<use href="#i-sun-bolt"/>'), 1)
        self.assertIn('ico-wx--risk', html)

    def test_full_density_states_the_condition_in_words(self):
        # Arrange
        event = self.create_event()
        forecast = self.create_forecast(hourly=[
            {'time': self.starts_at.strftime('%Y-%m-%dT%H:%M'), 'condition': 'sun', 'temperature': 24, 'aqhi': 4},
            {'time': (self.starts_at + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'sun', 'temperature': 24, 'aqhi': 4},
            {'time': (self.starts_at + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'thunder', 'temperature': 24, 'aqhi': 4},
        ])

        # Act
        html = render(
            '{% event_meta event density="full" forecast_state=state %}',
            event=event, state=ForecastState.ready(forecast),
        )

        # Assert
        self.assertIn('Sun / thunderstorms possible', html)

    def test_aqhi_change_across_the_window_uses_an_arrow(self):
        # Arrange
        event = self.create_event()
        forecast = self.create_forecast(hourly=[
            {'time': self.starts_at.strftime('%Y-%m-%dT%H:%M'), 'condition': 'sun', 'temperature': 24, 'aqhi': 2},
            {'time': (self.starts_at + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'sun', 'temperature': 24, 'aqhi': 2},
            {'time': (self.starts_at + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
             'condition': 'sun', 'temperature': 24, 'aqhi': 8},
        ])

        # Act
        html = render(
            '{% event_meta event forecast_state=state %}',
            event=event, state=ForecastState.ready(forecast),
        )

        # Assert
        self.assertIn('AQHI&nbsp;2', html)
        self.assertIn('wx-aqhi--low', html)
        self.assertIn('&rarr;8', html)
        self.assertIn('wx-aqhi--high', html)

    def test_pending_forecast_renders_the_meta_placeholder(self):
        # Arrange
        event = self.create_event()

        # Act
        html = render(
            '{% event_meta event forecast_state=state %}',
            event=event, state=ForecastState.pending_fetch(),
        )

        # Assert
        self.assertIn(f'id="forecast-badge-{event.id}"', html)
        self.assertIn('Loading weather forecast', html)
        self.assertIn('meta-item--weather', html)
        self.assertNotIn('meta-pill', html)

    def test_glyph_mapping_covers_every_condition(self):
        # Assert
        for condition in Forecast.Condition:
            self.assertIn(condition, design.WEATHER_GLYPHS)

    def test_every_warning_combination_maps_to_a_single_glyph(self):
        # Arrange
        severity = list(Forecast.Condition)
        notable = [Forecast.Condition.RAIN, Forecast.Condition.SNOW, Forecast.Condition.THUNDER]

        # Assert
        for primary in Forecast.Condition:
            for warning in notable:
                if severity.index(warning) <= severity.index(primary):
                    continue
                self.assertIn((primary, warning), design.WEATHER_COMPOSITE_GLYPHS)


class EventMetaLocationTests(DesignTagTestCase):
    def test_compact_truncates_a_long_venue(self):
        # Arrange
        event = self.create_event(location='The Very Long Named Community Centre And Recreation Complex')

        # Act
        html = render('{% event_meta event density="compact" %}', event=event)

        # Assert
        self.assertIn('meta-text--truncate', html)
        self.assertIn('The Very Long Named Community Centre And Recreation Complex', html)

    def test_full_does_not_truncate_a_long_venue(self):
        # Arrange
        event = self.create_event(location='The Very Long Named Community Centre And Recreation Complex')

        # Act
        html = render('{% event_meta event density="full" %}', event=event)

        # Assert
        self.assertNotIn('meta-text--truncate', html)
        self.assertIn('The Very Long Named Community Centre And Recreation Complex', html)

    def test_full_renders_the_location_as_a_link_with_a_chevron(self):
        # Arrange
        event = self.create_event(location_url='https://maps.example.com/park')

        # Act
        html = render('{% event_meta event density="full" %}', event=event)

        # Assert
        self.assertIn('href="https://maps.example.com/park"', html)
        self.assertIn('meta-item--link', html)
        self.assertIn('<use href="#i-chevron-right"/>', html)

    def test_compact_keeps_the_location_as_plain_text(self):
        # Arrange
        event = self.create_event(location_url='https://maps.example.com/park')

        # Act
        html = render('{% event_meta event density="compact" %}', event=event)

        # Assert
        self.assertNotIn('<a', html)

    def test_virtual_event_shows_the_platform(self):
        # Arrange
        event = self.create_event(virtual=True, location='Teams')

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertIn('Teams', html)
        self.assertIn('<use href="#i-monitor"/>', html)
        self.assertNotIn('<use href="#i-pin"/>', html)

    def test_virtual_event_without_a_venue_omits_the_location(self):
        # Arrange
        event = self.create_event(virtual=True, location='', location_url='')

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertNotIn('#i-monitor', html)
        self.assertNotIn('#i-pin', html)


class EventMetaTimeTests(DesignTagTestCase):
    def test_time_range_for_a_timed_event(self):
        # Arrange
        event = self.create_event()

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertIn('9:00 AM – 12:00 PM', html)

    def test_single_time_when_start_and_end_match(self):
        # Arrange
        event = self.create_event(ends_at=self.starts_at)

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertIn('9:00 AM', html)
        self.assertNotIn('9:00 AM – 9:00 AM', html)

    def test_single_day_all_day_event_reads_as_all_day(self):
        # Arrange
        event = self.create_event(all_day=True, ends_at=self.starts_at + timedelta(hours=8))

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertIn('All day', html)
        self.assertNotIn('9:00 AM', html)

    def test_multi_day_all_day_event_reads_as_a_date_range(self):
        # Arrange
        event = self.create_event(all_day=True, ends_at=self.starts_at + timedelta(days=2))

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertRegex(html, r'\w+ \d+ – \w+ \d+ · All day')

    def test_overnight_event_carries_the_end_date(self):
        # Arrange
        event = self.create_event(ends_at=self.starts_at + timedelta(hours=20))

        # Act
        html = render('{% event_meta event %}', event=event)

        # Assert
        self.assertRegex(html, r'9:00 AM – \w+ \d+, 5:00 AM')


class EventStatsTests(DesignTagTestCase):
    def confirm_registration(self, event, name):
        return Registration.objects.create(
            event=event, name=name, first_name=name, last_name='Rider',
            email=f'{name.lower()}@example.com', state=Registration.STATE_CONFIRMED,
        )

    def test_rides_and_distance_render_without_chrome(self):
        # Arrange
        event = self.create_event()
        self.add_ride(event, distance=40)
        self.add_ride(event, distance=70)

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertIn('2 rides', html)
        self.assertIn('40–70 km', html)
        self.assertNotIn('meta-pill', html)
        self.assertNotIn('badge', html)

    def test_zero_registrations_reads_as_an_invitation(self):
        # Arrange
        event = self.create_event()

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertIn('Be the first to register', html)
        self.assertNotIn('0 registered', html)
        self.assertIn('stat-item--invitation', html)

    def test_zero_registrations_is_silent_once_registration_closed(self):
        # Arrange
        event = self.create_event(registration_closes_at=timezone.now() - timedelta(hours=1))

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertNotIn('Be the first to register', html)
        self.assertNotIn('registered', html)

    def test_registration_count_renders_against_the_limit(self):
        # Arrange
        event = self.create_event(registration_limit=10)
        self.confirm_registration(event, 'Alex')

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertIn('1/10 registered', html)
        self.assertNotIn('Full', html)

    def test_capacity_reached_marks_full_without_a_pill(self):
        # Arrange
        event = self.create_event(registration_limit=2)
        self.confirm_registration(event, 'Alex')
        self.confirm_registration(event, 'Blair')

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertIn('2/2 registered', html)
        self.assertIn('stat-full', html)
        self.assertNotIn('program-pill', html)
        self.assertNotIn('meta-pill', html)

    def test_external_registration_hides_the_count(self):
        # Arrange
        event = self.create_event(external_registration_url='https://example.com/signup')
        self.confirm_registration(event, 'Alex')

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertNotIn('registered', html)

    def test_announced_event_hides_the_count(self):
        # Arrange
        event = self.create_event(state=Event.STATE_ANNOUNCED)
        self.confirm_registration(event, 'Alex')

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertNotIn('registered', html)

    def test_empty_stats_render_nothing(self):
        # Arrange
        event = self.create_event(external_registration_url='https://example.com/signup')

        # Act
        html = render('{% event_stats event %}', event=event)

        # Assert
        self.assertEqual(html.strip(), '')


class EventListSurfaceTests(DesignTagTestCase):
    def setUp(self):
        super().setUp()
        SpeedRange.objects.create(lower_limit=25, upper_limit=30)

    def test_card_renders_exactly_one_filled_pill(self):
        # Arrange
        event = self.create_event()
        self.add_ride(event, distance=50)

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertEqual(response.content.decode().count('class="program-pill'), 1)
        self.assertNotContains(response, 'meta-pill')
        self.assertContains(response, event.name)

    def test_card_carries_no_emoji(self):
        # Arrange
        self.create_event()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertIsNone(EMOJI.search(response.content.decode()))

    def test_card_meta_has_no_chrome(self):
        # Arrange
        self.create_event()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'event-meta--compact')
        self.assertContains(response, 'meta-item')
        self.assertNotContains(response, 'meta-pill-neutral')

    def test_card_uses_sprite_icons_only(self):
        # Arrange
        self.create_event()
        self.add_ride(self.create_event(name='Second'), distance=30)

        # Act
        body = self.client.get(reverse('upcoming')).content.decode()
        card_markup = body.split('id="events-container"')[1]

        # Assert
        self.assertIn('<use href="#i-pin"/>', card_markup)
        self.assertNotIn('<path', card_markup)
        self.assertNotIn('bi bi-bicycle', card_markup)

    def test_sprite_is_included_once(self):
        # Arrange
        self.create_event()

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, 'class="icon-sprite"', count=1)

    def test_day_named_program_is_not_repeated_under_the_day_header(self):
        # Arrange
        sunday = self.starts_at + timedelta(days=(6 - self.starts_at.weekday()) % 7)
        self.create_event(program=Program.objects.create(name='Sunday'), starts_at=sunday,
                          ends_at=sunday + timedelta(hours=3))

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertNotContains(response, 'program-pill--sunday')

    @override_flag('weather_forecast_badges', active=True)
    def test_weather_placeholder_sits_inside_the_meta_block(self):
        # Arrange
        event = self.create_event()
        self.add_ride(event)

        # Act
        response = self.client.get(reverse('upcoming'))

        # Assert
        self.assertContains(response, f'id="forecast-badge-{event.id}"')
        self.assertContains(response, 'meta-item--weather')
        self.assertNotContains(response, 'meta-pill')

    def test_list_ships_no_alpine_or_htmx_of_its_own(self):
        # Arrange
        self.create_event()

        # Act
        body = self.client.get(reverse('upcoming')).content.decode()
        card_markup = body.split('id="events-container"')[1]

        # Assert
        self.assertNotIn('x-data', card_markup)
        self.assertNotIn('hx-', card_markup)
