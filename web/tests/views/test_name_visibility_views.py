import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from backoffice.models import Event, Program, Registration, Ride, Route, SpeedRange, UserProfile

MASKED_NAME_PATTERN = re.compile(r'^[A-Z]\* [A-Z]\*$')


class BaseNameVisibilityTestCase(TestCase):
    def setUp(self):
        self.public_user = self._create_user('public@example.com', 'Pat', 'Public')
        self.only_users_user = self._create_user('users@example.com', 'Uma', 'Usersonly')
        self.only_users_user.profile.name_visibility = UserProfile.NameVisibility.ONLY_USERS
        self.only_users_user.profile.save()
        self.only_required_user = self._create_user('required@example.com', 'Rex', 'Requiredonly')
        self.only_required_user.profile.name_visibility = UserProfile.NameVisibility.ONLY_REQUIRED_USERS
        self.only_required_user.profile.save()

        self.viewer_user = self._create_user('viewer@example.com', 'Vic', 'Viewer')
        self.staff_user = self._create_user('staff@example.com', 'Sam', 'Staff')
        self.staff_user.is_staff = True
        self.staff_user.save()
        self.leader_user = self._create_user('leader@example.com', 'Lea', 'Leader')

        self.program = Program.objects.create(name='Test Program')

        now = timezone.now()
        self.event = Event.objects.create(
            program=self.program,
            name='Test Event',
            starts_at=now + timedelta(days=7),
            registration_closes_at=now + timedelta(days=6),
            ride_leaders_wanted=True,
        )

        self.route = Route.objects.create(name='Test Route')
        self.ride = Ride.objects.create(name='Test Ride', event=self.event, route=self.route)
        self.speed_range = SpeedRange.objects.create(lower_limit=25, upper_limit=30)
        self.ride.speed_ranges.add(self.speed_range)

        self.public_registration = self._create_registration(self.public_user)
        self.only_users_registration = self._create_registration(self.only_users_user)
        self.only_required_registration = self._create_registration(self.only_required_user)
        self.leader_registration = self._create_registration(
            self.leader_user,
            ride_leader_preference=Registration.RideLeaderPreference.YES,
        )

    def _create_user(self, email, first_name, last_name):
        return User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )

    def _create_registration(self, user, ride_leader_preference=Registration.RideLeaderPreference.NO):
        return Registration.objects.create(
            first_name=user.first_name,
            last_name=user.last_name,
            name=f"{user.first_name} {user.last_name}",
            email=user.email,
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=ride_leader_preference,
            user=user,
            state=Registration.STATE_CONFIRMED,
        )

    def _rider_names_from_detail(self, response):
        names = []
        for ride_info in response.context['rides'].values():
            for speed_range_info in ride_info['speed_ranges'].values():
                names.extend(rider.name for rider in speed_range_info['riders'])
        return names

    def _assert_masked(self, name):
        self.assertRegex(name, MASKED_NAME_PATTERN)


class EventDetailNameVisibilityTests(BaseNameVisibilityTestCase):
    def _get_detail_names(self):
        response = self.client.get(reverse('event_detail', args=[self.event.id]))
        self.assertEqual(response.status_code, 200)
        return self._rider_names_from_detail(response)

    def test_anonymous_viewer_sees_public_name_only(self):
        # Act
        names = self._get_detail_names()

        # Assert
        self.assertIn('Pat Public', names)
        self.assertIn('Lea Leader', names)
        self.assertNotIn('Uma Usersonly', names)
        self.assertNotIn('Rex Requiredonly', names)

    def test_anonymous_viewer_sees_masked_names_for_hidden_riders(self):
        # Act
        names = self._get_detail_names()

        # Assert
        masked = [name for name in names if MASKED_NAME_PATTERN.match(name)]
        self.assertEqual(len(masked), 2)

    def test_anonymous_viewer_counts_include_masked_riders(self):
        # Act
        response = self.client.get(reverse('event_detail', args=[self.event.id]))

        # Assert
        speed_range_info = response.context['rides'][str(self.ride.id)]['speed_ranges'][str(self.speed_range.id)]
        self.assertEqual(len(speed_range_info['riders']), 4)
        self.assertEqual(speed_range_info['ride_leader_count'], 1)
        self.assertEqual(speed_range_info['non_leader_count'], 3)

    def test_signed_in_viewer_sees_only_users_name(self):
        # Arrange
        self.client.force_login(self.viewer_user)

        # Act
        names = self._get_detail_names()

        # Assert
        self.assertIn('Pat Public', names)
        self.assertIn('Uma Usersonly', names)
        self.assertNotIn('Rex Requiredonly', names)

    def test_staff_viewer_sees_all_names(self):
        # Arrange
        self.client.force_login(self.staff_user)

        # Act
        names = self._get_detail_names()

        # Assert
        self.assertIn('Pat Public', names)
        self.assertIn('Uma Usersonly', names)
        self.assertIn('Rex Requiredonly', names)

    def test_ride_leader_viewer_sees_all_names(self):
        # Arrange
        self.client.force_login(self.leader_user)

        # Act
        names = self._get_detail_names()

        # Assert
        self.assertIn('Pat Public', names)
        self.assertIn('Uma Usersonly', names)
        self.assertIn('Rex Requiredonly', names)

    def test_registration_without_user_is_masked_for_anonymous_viewer(self):
        # Arrange
        Registration.objects.create(
            first_name='Nora',
            last_name='Nouser',
            name='Nora Nouser',
            email='nouser@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RideLeaderPreference.NO,
            state=Registration.STATE_CONFIRMED,
        )

        # Act
        names = self._get_detail_names()

        # Assert
        self.assertNotIn('Nora Nouser', names)
        self.assertIn('N* N*', names)

    def test_registration_without_user_is_visible_to_staff(self):
        # Arrange
        Registration.objects.create(
            first_name='Nora',
            last_name='Nouser',
            name='Nora Nouser',
            email='nouser@example.com',
            event=self.event,
            ride=self.ride,
            speed_range_preference=self.speed_range,
            ride_leader_preference=Registration.RideLeaderPreference.NO,
            state=Registration.STATE_CONFIRMED,
        )
        self.client.force_login(self.staff_user)

        # Act
        names = self._get_detail_names()

        # Assert
        self.assertIn('Nora Nouser', names)


class RidersListNameVisibilityTests(BaseNameVisibilityTestCase):
    def _get_riders_list_names(self):
        response = self.client.get(reverse('riders_list', args=[self.event.id]))
        self.assertEqual(response.status_code, 200)
        return [rider.name for rider in response.context['filtered_riders']]

    def test_anonymous_viewer_sees_masked_names(self):
        # Act
        names = self._get_riders_list_names()

        # Assert
        self.assertEqual(len(names), 4)
        self.assertIn('Pat Public', names)
        self.assertNotIn('Uma Usersonly', names)
        self.assertNotIn('Rex Requiredonly', names)

    def test_signed_in_viewer_sees_only_users_name(self):
        # Arrange
        self.client.force_login(self.viewer_user)

        # Act
        names = self._get_riders_list_names()

        # Assert
        self.assertIn('Uma Usersonly', names)
        self.assertNotIn('Rex Requiredonly', names)

    def test_staff_viewer_sees_all_names(self):
        # Arrange
        self.client.force_login(self.staff_user)

        # Act
        names = self._get_riders_list_names()

        # Assert
        self.assertIn('Pat Public', names)
        self.assertIn('Uma Usersonly', names)
        self.assertIn('Rex Requiredonly', names)

    def test_ride_leader_viewer_sees_all_names(self):
        # Arrange
        self.client.force_login(self.leader_user)

        # Act
        names = self._get_riders_list_names()

        # Assert
        self.assertIn('Uma Usersonly', names)
        self.assertIn('Rex Requiredonly', names)


class ProfileNameVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='member@example.com',
            email='member@example.com',
            first_name='Member',
            last_name='User',
        )

    def test_profile_page_shows_current_name_visibility(self):
        # Arrange
        self.client.force_login(self.user)

        # Act
        response = self.client.get(reverse('profile'))

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['name_visibility'], UserProfile.NameVisibility.PUBLIC)
        self.assertContains(response, 'When can we show your name on registration lists?')

    def test_post_updates_name_visibility(self):
        # Arrange
        self.client.force_login(self.user)

        # Act
        response = self.client.post(
            reverse('profile_name_visibility'),
            {'name_visibility': UserProfile.NameVisibility.ONLY_REQUIRED_USERS},
        )

        # Assert
        self.assertRedirects(response, reverse('profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.name_visibility, UserProfile.NameVisibility.ONLY_REQUIRED_USERS)

    def test_post_with_invalid_choice_leaves_preference_unchanged(self):
        # Arrange
        self.client.force_login(self.user)

        # Act
        response = self.client.post(reverse('profile_name_visibility'), {'name_visibility': 'xx'})

        # Assert
        self.assertRedirects(response, reverse('profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.name_visibility, UserProfile.NameVisibility.PUBLIC)

    def test_post_requires_login(self):
        # Act
        response = self.client.post(
            reverse('profile_name_visibility'),
            {'name_visibility': UserProfile.NameVisibility.ONLY_USERS},
        )

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
