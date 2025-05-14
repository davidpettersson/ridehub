import datetime

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from backoffice.models import Event, Registration, Program
from backoffice.services.registration_service import RegistrationService


class FetchCurrentRegistrationsTestCase(TestCase):
    def setUp(self):
        # Arrange: Common setup for most tests
        self.service = RegistrationService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.program = Program.objects.create(
            name="Test Program"
        )
        self.test_today_date = timezone.now().date()
        self.noon_time = datetime.time(12, 0, 0) # Store noon_time for re-use
        self.test_today_datetime_noon = timezone.make_aware( # Renamed for clarity
            datetime.datetime.combine(self.test_today_date, self.noon_time)
        )

    def test_fetch_current_registrations(self):
        # Arrange: Specific events and registrations for this test
        past_event = Event.objects.create(
            name="Past Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=2)
        )
        Registration.objects.create( # Past registration, should not be fetched
            user=self.user,
            event=past_event,
            name=self.user.username,
            email=self.user.email
        )
        
        today_event_noon = Event.objects.create(
            name="Today Event (noon)",
            program=self.program,
            starts_at=self.test_today_datetime_noon,
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(hours=1)
        )
        reg_today_noon = Registration.objects.create(
            user=self.user,
            event=today_event_noon,
            name=self.user.username,
            email=self.user.email
        )

        future_event_tomorrow = Event.objects.create(
            name="Future Event 1 (Tomorrow)",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon
        )
        reg_future_tomorrow = Registration.objects.create(
            user=self.user,
            event=future_event_tomorrow,
            name=self.user.username,
            email=self.user.email
        )

        future_event_day_after = Event.objects.create(
            name="Future Event 2 (Day after tomorrow)",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=2),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=1)
        )
        reg_future_day_after = Registration.objects.create(
            user=self.user,
            event=future_event_day_after,
            name=self.user.username,
            email=self.user.email
        )

        # Act
        current_registrations = self.service.fetch_current_registrations(self.user)

        # Assert
        self.assertEqual(len(current_registrations), 3)
        self.assertIn(reg_today_noon, current_registrations)
        self.assertIn(reg_future_tomorrow, current_registrations)
        self.assertIn(reg_future_day_after, current_registrations)

        # Assuming the service method returns registrations ordered by event start time
        self.assertEqual(current_registrations[0], reg_today_noon)
        self.assertEqual(current_registrations[1], reg_future_tomorrow)
        self.assertEqual(current_registrations[2], reg_future_day_after)

    def test_fetch_current_registrations_no_registrations(self):
        # Arrange
        new_user_no_regs = User.objects.create_user(
            username='newuser_no_regs',
            email='newuser_no_regs@example.com',
            password='password'
        )
        # No registrations created for this user

        # Act
        current_registrations = self.service.fetch_current_registrations(new_user_no_regs)

        # Assert
        self.assertEqual(len(current_registrations), 0)

    def test_fetch_current_registrations_only_past_registration(self):
        # Arrange
        user_past_reg_only = User.objects.create_user(
            username='user_past_reg_only',
            email='user_past_reg_only@example.com',
            password='password'
        )
        past_event = Event.objects.create(
            name="Only Past Event",
            program=self.program, # Can use self.program from setUp
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        Registration.objects.create(
            user=user_past_reg_only,
            event=past_event,
            name=user_past_reg_only.username,
            email=user_past_reg_only.email
        )

        # Act
        current_registrations = self.service.fetch_current_registrations(user_past_reg_only)

        # Assert
        self.assertEqual(len(current_registrations), 0)

    def test_fetch_current_registrations_event_earlier_today(self):
        # Arrange
        eight_am_time = datetime.time(8, 0, 0)
        event_starts_earlier_today_datetime = timezone.make_aware(
            datetime.datetime.combine(self.test_today_date, eight_am_time)
        )
        event_today_8am = Event.objects.create(
            name="Today Event (8 AM)",
            program=self.program,
            starts_at=event_starts_earlier_today_datetime,
            registration_closes_at=event_starts_earlier_today_datetime - datetime.timedelta(hours=1)
        )
        reg_today_8am = Registration.objects.create(
            user=self.user, # Using self.user from setUp
            event=event_today_8am,
            name=self.user.username,
            email=self.user.email
        )

        # Also create a noon event for self.user for comprehensive testing
        today_event_noon = Event.objects.create(
            name="Today Event (noon) for 8am test",
            program=self.program,
            starts_at=self.test_today_datetime_noon,
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(hours=1)
        )
        reg_today_noon = Registration.objects.create(
            user=self.user,
            event=today_event_noon,
            name=self.user.username,
            email=self.user.email
        )
        
        # And a future event
        future_event_tomorrow = Event.objects.create(
            name="Future Event for 8am test",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon
        )
        reg_future_tomorrow = Registration.objects.create(
            user=self.user,
            event=future_event_tomorrow,
            name=self.user.username,
            email=self.user.email
        )


        # Act
        current_registrations = self.service.fetch_current_registrations(self.user)
        
        # Assert
        self.assertEqual(len(current_registrations), 3) 
        self.assertIn(reg_today_8am, current_registrations)
        self.assertIn(reg_today_noon, current_registrations)
        self.assertIn(reg_future_tomorrow, current_registrations)
        
        registrations_sorted = sorted(current_registrations, key=lambda r: r.event.starts_at)
        self.assertEqual(registrations_sorted[0], reg_today_8am)
        self.assertEqual(registrations_sorted[1], reg_today_noon)
        self.assertEqual(registrations_sorted[2], reg_future_tomorrow)


    def test_fetch_current_registrations_future_registration_isolated(self):
        # Arrange: User with only one future registration
        user_future_only = User.objects.create_user(
            username='user_future_only',
            email='user_future_only@example.com',
            password='password'
        )
        future_event_specific = Event.objects.create(
            name="Specific Future Event (Isolated)",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=3),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=2)
        )
        reg_future_specific = Registration.objects.create(
            user=user_future_only,
            event=future_event_specific,
            name=user_future_only.username,
            email=user_future_only.email
        )

        # Act
        current_registrations = self.service.fetch_current_registrations(user_future_only)

        # Assert
        self.assertEqual(len(current_registrations), 1)
        self.assertIn(reg_future_specific, current_registrations)
        self.assertEqual(current_registrations[0], reg_future_specific)


    def test_fetch_current_registrations_other_user_event_not_shown(self):
        # Arrange: Setup self.user's registrations
        today_event_noon = Event.objects.create(
            name="Today Event (noon) for other user test",
            program=self.program,
            starts_at=self.test_today_datetime_noon,
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(hours=1)
        )
        reg_today_noon_self = Registration.objects.create(
            user=self.user,
            event=today_event_noon,
            name=self.user.username,
            email=self.user.email
        )
        future_event_tomorrow = Event.objects.create(
            name="Future Event (Tomorrow) for other user test",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon
        )
        reg_future_tomorrow_self = Registration.objects.create(
            user=self.user,
            event=future_event_tomorrow,
            name=self.user.username,
            email=self.user.email
        )

        # Arrange: Setup other_user and their registration
        other_user = User.objects.create_user(
            username='otheruser_test',
            email='otheruser_test@example.com',
            password='password'
        )
        event_for_other_user = Event.objects.create(
            name="Other User's Future Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1), 
            registration_closes_at=self.test_today_datetime_noon
        )
        reg_other_user = Registration.objects.create(
            user=other_user,
            event=event_for_other_user,
            name=other_user.username,
            email=other_user.email
        )

        # Act: Fetch registrations for self.user
        current_registrations_for_self_user = self.service.fetch_current_registrations(self.user)
        
        # Assert: Ensure only self.user's registrations are returned
        self.assertEqual(len(current_registrations_for_self_user), 2)
        self.assertIn(reg_today_noon_self, current_registrations_for_self_user)
        self.assertIn(reg_future_tomorrow_self, current_registrations_for_self_user)
        self.assertNotIn(reg_other_user, current_registrations_for_self_user)

        for reg in current_registrations_for_self_user:
            self.assertEqual(reg.user, self.user)