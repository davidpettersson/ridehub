from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program, Registration, Ride, Route, SpeedRange
from web.filters import PublicRegistrationFilter, RegistrationFilter


class BaseFilterTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.program = Program.objects.create(name="Test Program")

        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=now + timezone.timedelta(days=7),
            ends_at=now + timezone.timedelta(days=7, hours=4),
            registration_closes_at=now + timezone.timedelta(days=6),
        )

        self.other_event = Event.objects.create(
            name="Other Event",
            program=self.program,
            starts_at=now + timezone.timedelta(days=14),
            ends_at=now + timezone.timedelta(days=14, hours=4),
            registration_closes_at=now + timezone.timedelta(days=13),
        )

        self.route = Route.objects.create(name="Test Route")

        self.ride_a = Ride.objects.create(
            name="Ride A", event=self.event, route=self.route, ordering=1
        )
        self.ride_b = Ride.objects.create(
            name="Ride B", event=self.event, route=self.route, ordering=2
        )
        self.other_ride = Ride.objects.create(
            name="Other Ride", event=self.other_event, route=self.route, ordering=1
        )

        self.speed_slow = SpeedRange.objects.create(lower_limit=20, upper_limit=25)
        self.speed_fast = SpeedRange.objects.create(lower_limit=30, upper_limit=35)
        self.speed_other = SpeedRange.objects.create(lower_limit=40, upper_limit=45)

        self.ride_a.speed_ranges.add(self.speed_slow, self.speed_fast)
        self.ride_b.speed_ranges.add(self.speed_slow, self.speed_fast)
        self.other_ride.speed_ranges.add(self.speed_other)

        self.user_a = User.objects.create_user(
            username='user_a', email='usera@example.com', password='pass',
            first_name='Alice', last_name='Alpha',
        )
        self.user_b = User.objects.create_user(
            username='user_b', email='userb@example.com', password='pass',
            first_name='Bob', last_name='Beta',
        )
        self.user_c = User.objects.create_user(
            username='user_c', email='userc@example.com', password='pass',
            first_name='Carol', last_name='Gamma',
        )

        self.reg_a = self._create_registration(
            self.user_a, self.ride_a, self.speed_slow,
            Registration.RideLeaderPreference.YES,
        )
        self.reg_b = self._create_registration(
            self.user_b, self.ride_b, self.speed_fast,
            Registration.RideLeaderPreference.NO,
        )
        self.reg_c = self._create_registration(
            self.user_c, self.ride_a, self.speed_fast,
            Registration.RideLeaderPreference.NO,
        )

        self.base_qs = Registration.objects.filter(
            event=self.event, state=Registration.STATE_CONFIRMED,
        )

    def _create_registration(self, user, ride, speed_range, leader_pref):
        reg = Registration.objects.create(
            event=self.event,
            user=user,
            name=user.get_full_name(),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            phone='+16135550100',
            ride=ride,
            speed_range_preference=speed_range,
            ride_leader_preference=leader_pref,
        )
        reg.confirm()
        reg.save()
        return reg


class PublicRegistrationFilterTests(BaseFilterTestCase):
    def test_filter_by_ride(self):
        # Arrange
        data = {'ride': self.ride_a.id}

        # Act
        f = PublicRegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertIn(self.reg_a.id, result_ids)
        self.assertIn(self.reg_c.id, result_ids)
        self.assertNotIn(self.reg_b.id, result_ids)

    def test_filter_by_speed_range(self):
        # Arrange
        data = {'speed_range_preference': self.speed_slow.id}

        # Act
        f = PublicRegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertIn(self.reg_a.id, result_ids)
        self.assertNotIn(self.reg_b.id, result_ids)
        self.assertNotIn(self.reg_c.id, result_ids)

    def test_filter_by_ride_leader(self):
        # Arrange
        data = {'ride_leader_preference': 'y'}

        # Act
        f = PublicRegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertIn(self.reg_a.id, result_ids)
        self.assertNotIn(self.reg_b.id, result_ids)
        self.assertNotIn(self.reg_c.id, result_ids)

    def test_no_filters_returns_all(self):
        # Arrange
        data = {}

        # Act
        f = PublicRegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        self.assertEqual(f.qs.count(), 3)

    def test_speed_range_queryset_scoped_to_event(self):
        # Arrange / Act
        f = PublicRegistrationFilter({}, queryset=self.base_qs, event=self.event)

        # Assert
        speed_qs = f.filters['speed_range_preference'].queryset
        self.assertIn(self.speed_slow, speed_qs)
        self.assertIn(self.speed_fast, speed_qs)
        self.assertNotIn(self.speed_other, speed_qs)

    def test_ride_queryset_scoped_to_event(self):
        # Arrange / Act
        f = PublicRegistrationFilter({}, queryset=self.base_qs, event=self.event)

        # Assert
        ride_qs = f.filters['ride'].queryset
        self.assertIn(self.ride_a, ride_qs)
        self.assertIn(self.ride_b, ride_qs)
        self.assertNotIn(self.other_ride, ride_qs)

    def test_combined_filters(self):
        # Arrange
        data = {'ride': self.ride_a.id, 'ride_leader_preference': 'y'}

        # Act
        f = PublicRegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertEqual(result_ids, {self.reg_a.id})


class RegistrationFilterTests(BaseFilterTestCase):
    def test_search_by_name(self):
        # Arrange
        data = {'search': 'Alice'}

        # Act
        f = RegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertIn(self.reg_a.id, result_ids)
        self.assertNotIn(self.reg_b.id, result_ids)

    def test_search_by_email(self):
        # Arrange
        data = {'search': 'userb@example.com'}

        # Act
        f = RegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertIn(self.reg_b.id, result_ids)
        self.assertNotIn(self.reg_a.id, result_ids)

    def test_filter_by_ride(self):
        # Arrange
        data = {'ride': self.ride_b.id}

        # Act
        f = RegistrationFilter(data, queryset=self.base_qs, event=self.event)

        # Assert
        result_ids = set(f.qs.values_list('id', flat=True))
        self.assertIn(self.reg_b.id, result_ids)
        self.assertNotIn(self.reg_a.id, result_ids)
        self.assertNotIn(self.reg_c.id, result_ids)
