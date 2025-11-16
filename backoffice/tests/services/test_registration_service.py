import datetime

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone

from backoffice.models import Event, Registration, Program, UserProfile
from backoffice.services.registration_service import RegistrationService, UserDetail, RegistrationDetail
from backoffice.services.request_service import RequestDetail

from django.core import mail
from django.urls import reverse
from django.conf import settings


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

    def test_fetch_current_registrations_excludes_archived_events(self):
        # Arrange
        # Non-archived event and registration (should be included)
        event_not_archived = Event.objects.create(
            name="Current Event Not Archived",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon,
            archived=False
        )
        reg_not_archived = Registration.objects.create(
            user=self.user,
            event=event_not_archived,
            name=self.user.username,
            email=self.user.email
        )

        # Archived event and registration (should be excluded)
        event_archived = Event.objects.create(
            name="Current Event Archived",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=2),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            archived=True
        )
        Registration.objects.create(
            user=self.user,
            event=event_archived,
            name=self.user.username,
            email=self.user.email
        )

        # Act
        current_registrations = self.service.fetch_current_registrations(self.user)

        # Assert
        self.assertEqual(len(current_registrations), 1)
        self.assertIn(reg_not_archived, current_registrations)
        self.assertEqual(current_registrations[0], reg_not_archived)

    def test_fetch_current_registrations_gets_latest_for_multiple_on_same_event(self):
        # Arrange
        # Event for which user will have multiple registrations
        multi_reg_event = Event.objects.create(
            name="Event with Multiple Registrations",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon,
            archived=False
        )

        # Older registration for multi_reg_event (created first, lower pk)
        Registration.objects.create(
            user=self.user,
            event=multi_reg_event,
            name=self.user.username,
            email=self.user.email
        )

        # Newer registration for multi_reg_event (created second, higher pk)
        reg_newer_for_multi_event = Registration.objects.create(
            user=self.user,
            event=multi_reg_event,
            name=self.user.username,
            email=self.user.email # Using same email, but different registration pk
        )

        # Another distinct current event and registration, for control
        other_current_event = Event.objects.create(
            name="Another Single Current Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=2),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            archived=False
        )
        reg_other_single = Registration.objects.create(
            user=self.user,
            event=other_current_event,
            name=self.user.username,
            email=self.user.email
        )

        # Act
        current_registrations = self.service.fetch_current_registrations(self.user)

        # Assert
        self.assertEqual(len(current_registrations), 2)
        self.assertIn(reg_newer_for_multi_event, current_registrations)
        self.assertIn(reg_other_single, current_registrations)
        
        # Ensure the older registration for multi_reg_event is not present
        registrations_on_multi_event = [reg for reg in current_registrations if reg.event == multi_reg_event]
        self.assertEqual(len(registrations_on_multi_event), 1)
        self.assertEqual(registrations_on_multi_event[0], reg_newer_for_multi_event)

        # Check overall order if desired (assuming event__starts_at ordering)
        # multi_reg_event (days=1) should come before other_current_event (days=2)
        sorted_regs = sorted(list(current_registrations), key=lambda r: r.event.starts_at)
        self.assertEqual(sorted_regs[0], reg_newer_for_multi_event)
        self.assertEqual(sorted_regs[1], reg_other_single)

    def test_fetch_current_registrations_only_confirmed_and_submitted(self):
        # Arrange
        # Create an event
        event = Event.objects.create(
            name="Event for Registration State Test",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon,
            archived=False
        )
        
        # Create a submitted registration
        reg_submitted = Registration.objects.create(
            user=self.user,
            event=event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        
        # Create a confirmed registration for another event
        event_confirmed = Event.objects.create(
            name="Event for Confirmed Registration",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=2),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            archived=False
        )
        reg_confirmed = Registration.objects.create(
            user=self.user,
            event=event_confirmed,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_confirmed.confirm()
        reg_confirmed.save()
        
        # Create a withdrawn registration that should not be included
        event_withdrawn = Event.objects.create(
            name="Event for Withdrawn Registration",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=3),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=2),
            archived=False
        )
        reg_withdrawn = Registration.objects.create(
            user=self.user,
            event=event_withdrawn,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_withdrawn.confirm()
        reg_withdrawn.withdraw()
        reg_withdrawn.save()

        # Act
        current_registrations = self.service.fetch_current_registrations(self.user)

        # Assert
        self.assertEqual(len(current_registrations), 2)
        self.assertIn(reg_submitted, current_registrations)
        self.assertIn(reg_confirmed, current_registrations)
        self.assertNotIn(reg_withdrawn, current_registrations)
        
        # Verify states - all should be either 'submitted' or 'confirmed'
        for registration in current_registrations:
            self.assertIn(registration.state, [Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED])

    def test_fetch_current_registrations_multiple_for_same_event_filters_by_state(self):
        # Arrange
        # Create a single event
        event = Event.objects.create(
            name="Event with Multiple Registration States",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon,
            archived=False
        )
        
        # First registration - Submitted (oldest)
        Registration.objects.create(
            user=self.user,
            event=event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        
        # Second registration - Confirmed (middle)
        reg_confirmed = Registration.objects.create(
            user=self.user,
            event=event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_confirmed.confirm()
        reg_confirmed.save()
        
        # Third registration - Withdrawn (newest, but should be excluded)
        reg_withdrawn = Registration.objects.create(
            user=self.user,
            event=event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_withdrawn.confirm()
        reg_withdrawn.withdraw()
        reg_withdrawn.save()
        
        # Fourth registration - Confirmed (newest valid state)
        reg_newest = Registration.objects.create(
            user=self.user,
            event=event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_newest.confirm()
        reg_newest.save()

        # Act
        current_registrations = self.service.fetch_current_registrations(self.user)

        # Assert
        self.assertEqual(len(current_registrations), 1)
        self.assertIn(reg_newest, current_registrations)
        self.assertNotIn(reg_withdrawn, current_registrations)
        
        # Verify we got the newest valid registration
        registrations_for_event = [reg for reg in current_registrations if reg.event == event]
        self.assertEqual(len(registrations_for_event), 1)
        self.assertEqual(registrations_for_event[0], reg_newest)
        
        # Verify state is valid
        self.assertIn(registrations_for_event[0].state, [Registration.STATE_SUBMITTED, Registration.STATE_CONFIRMED])


class RegistrationServiceEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser_email', email='test_email@example.com', password='password')
        self.user.profile.phone = "+16131112222"
        self.user.profile.save()
        self.program = Program.objects.create(name="Email Test Program")
        self.event = Event.objects.create(
            program=self.program,
            name="Email Test Event",
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            ride_leaders_wanted=True,
            requires_emergency_contact=True # Assuming this is needed for RegistrationDetail
        )
        self.service = RegistrationService()
        mail.outbox = []

    def test_confirmation_email_links_for_regular_user(self):
        # Arrange
        user_detail = UserDetail(first_name="Test", last_name="User", email=self.user.email, phone="+16131112222")
        registration_detail = RegistrationDetail(
            ride=None, 
            ride_leader_preference=Registration.RideLeaderPreference.NO,
            speed_range_preference=None,
            emergency_contact_name="EC Name", # Added dummy emergency contact
            emergency_contact_phone="1234567890" # Added dummy emergency contact
        )

        # Act
        self.service.register(user_detail, registration_detail, self.event)

        # Assert
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        expected_profile_url = f"https://{settings.WEB_HOST}{reverse('profile')}"
        
        # HTML part (if multipart)
        if email.alternatives:
            html_body = email.alternatives[0][0]
            self.assertIn(f'href="{expected_profile_url}"', html_body)
            unexpected_riders_url_path = reverse('riders_list', args=[self.event.id])
            self.assertNotIn(unexpected_riders_url_path, html_body)
        else:
            self.fail("Email does not have an HTML alternative part.")

        # Plain text part
        text_body = email.body
        self.assertIn(expected_profile_url, text_body)
        unexpected_riders_url_path_text = reverse('riders_list', args=[self.event.id])
        self.assertNotIn(unexpected_riders_url_path_text, text_body)

    def test_confirmation_email_links_for_ride_leader(self):
        # Arrange
        # Create a new user for this test to ensure isolation if needed, or reuse self.user
        ride_leader_user = User.objects.create_user(username='testleader_email', email='test_leader_email@example.com', password='password')
        user_detail = UserDetail(first_name="Test", last_name="Leader", email=ride_leader_user.email, phone="+16131112222")
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=Registration.RideLeaderPreference.YES,
            speed_range_preference=None,
            emergency_contact_name="EC Leader Name", # Added dummy emergency contact
            emergency_contact_phone="0987654321" # Added dummy emergency contact
        )

        # Act
        self.service.register(user_detail, registration_detail, self.event)

        # Assert
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        expected_profile_url = f"https://{settings.WEB_HOST}{reverse('profile')}"
        expected_riders_list_url = f"https://{settings.WEB_HOST}{reverse('riders_list', args=[self.event.id])}"

        # HTML part
        if email.alternatives:
            html_body = email.alternatives[0][0]
            self.assertIn(f'href="{expected_profile_url}"', html_body)
            self.assertIn(f'href="{expected_riders_list_url}"', html_body)
            self.assertIn(f'<a href="{expected_riders_list_url}">Emergency Contact List</a>', html_body)
        else:
            self.fail("Email does not have an HTML alternative part.")

        # Plain text part
        text_body = email.body
        self.assertIn(expected_profile_url, text_body)
        self.assertIn(expected_riders_list_url, text_body)


class FetchPastRegistrationsTestCase(TestCase):
    def setUp(self):
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
        self.noon_time = datetime.time(12, 0, 0)
        self.test_today_datetime_noon = timezone.make_aware(
            datetime.datetime.combine(self.test_today_date, self.noon_time)
        )

    def test_fetch_past_registrations(self):
        past_event_1 = Event.objects.create(
            name="Past Event 1",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=11)
        )
        reg_past_1 = Registration.objects.create(
            user=self.user,
            event=past_event_1,
            name=self.user.username,
            email=self.user.email
        )

        past_event_2 = Event.objects.create(
            name="Past Event 2",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        reg_past_2 = Registration.objects.create(
            user=self.user,
            event=past_event_2,
            name=self.user.username,
            email=self.user.email
        )

        future_event = Event.objects.create(
            name="Future Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            ends_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon
        )
        Registration.objects.create(
            user=self.user,
            event=future_event,
            name=self.user.username,
            email=self.user.email
        )

        past_registrations = self.service.fetch_past_registrations(self.user)

        self.assertEqual(len(past_registrations), 2)
        self.assertIn(reg_past_1, past_registrations)
        self.assertIn(reg_past_2, past_registrations)

        self.assertEqual(past_registrations[0], reg_past_2)
        self.assertEqual(past_registrations[1], reg_past_1)

    def test_fetch_past_registrations_no_past_registrations(self):
        new_user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='password'
        )

        past_registrations = self.service.fetch_past_registrations(new_user)

        self.assertEqual(len(past_registrations), 0)

    def test_fetch_past_registrations_only_future_registrations(self):
        future_event = Event.objects.create(
            name="Future Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            ends_at=self.test_today_datetime_noon + datetime.timedelta(days=1),
            registration_closes_at=self.test_today_datetime_noon
        )
        Registration.objects.create(
            user=self.user,
            event=future_event,
            name=self.user.username,
            email=self.user.email
        )

        past_registrations = self.service.fetch_past_registrations(self.user)

        self.assertEqual(len(past_registrations), 0)

    def test_fetch_past_registrations_gets_latest_for_multiple_on_same_event(self):
        past_event = Event.objects.create(
            name="Past Event with Multiple Registrations",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )

        Registration.objects.create(
            user=self.user,
            event=past_event,
            name=self.user.username,
            email=self.user.email
        )

        reg_newer = Registration.objects.create(
            user=self.user,
            event=past_event,
            name=self.user.username,
            email=self.user.email
        )

        past_registrations = self.service.fetch_past_registrations(self.user)

        self.assertEqual(len(past_registrations), 1)
        self.assertIn(reg_newer, past_registrations)

        registrations_for_event = [reg for reg in past_registrations if reg.event == past_event]
        self.assertEqual(len(registrations_for_event), 1)
        self.assertEqual(registrations_for_event[0], reg_newer)

    def test_fetch_past_registrations_other_user_not_shown(self):
        past_event = Event.objects.create(
            name="Past Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        reg_self = Registration.objects.create(
            user=self.user,
            event=past_event,
            name=self.user.username,
            email=self.user.email
        )

        other_user = User.objects.create_user(
            username='otheruser',
            email='otheruser@example.com',
            password='password'
        )
        reg_other = Registration.objects.create(
            user=other_user,
            event=past_event,
            name=other_user.username,
            email=other_user.email
        )

        past_registrations = self.service.fetch_past_registrations(self.user)

        self.assertEqual(len(past_registrations), 1)
        self.assertIn(reg_self, past_registrations)
        self.assertNotIn(reg_other, past_registrations)

        for reg in past_registrations:
            self.assertEqual(reg.user, self.user)


class FetchUserStatisticsTestCase(TestCase):
    def setUp(self):
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
        self.noon_time = datetime.time(12, 0, 0)
        self.test_today_datetime_noon = timezone.make_aware(
            datetime.datetime.combine(self.test_today_date, self.noon_time)
        )

    def test_fetch_user_statistics_no_registrations(self):
        statistics = self.service.fetch_user_statistics(self.user)

        self.assertEqual(statistics['total_events_attended'], 0)
        self.assertEqual(statistics['times_as_ride_leader'], 0)

    def test_fetch_user_statistics_with_confirmed_registrations(self):
        past_event_1 = Event.objects.create(
            name="Past Event 1",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=11)
        )
        reg_1 = Registration.objects.create(
            user=self.user,
            event=past_event_1,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_1.confirm()
        reg_1.save()

        past_event_2 = Event.objects.create(
            name="Past Event 2",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        reg_2 = Registration.objects.create(
            user=self.user,
            event=past_event_2,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED
        )
        reg_2.confirm()
        reg_2.save()

        statistics = self.service.fetch_user_statistics(self.user)

        self.assertEqual(statistics['total_events_attended'], 2)
        self.assertEqual(statistics['times_as_ride_leader'], 0)

    def test_fetch_user_statistics_with_ride_leader_registrations(self):
        past_event_1 = Event.objects.create(
            name="Past Event 1",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=11)
        )
        reg_1 = Registration.objects.create(
            user=self.user,
            event=past_event_1,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )
        reg_1.confirm()
        reg_1.save()

        past_event_2 = Event.objects.create(
            name="Past Event 2",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        reg_2 = Registration.objects.create(
            user=self.user,
            event=past_event_2,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.NO
        )
        reg_2.confirm()
        reg_2.save()

        past_event_3 = Event.objects.create(
            name="Past Event 3",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=3),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=3),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=4)
        )
        reg_3 = Registration.objects.create(
            user=self.user,
            event=past_event_3,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )
        reg_3.confirm()
        reg_3.save()

        statistics = self.service.fetch_user_statistics(self.user)

        self.assertEqual(statistics['total_events_attended'], 3)
        self.assertEqual(statistics['times_as_ride_leader'], 2)

    def test_fetch_user_statistics_excludes_future_events(self):
        past_event = Event.objects.create(
            name="Past Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        reg_past = Registration.objects.create(
            user=self.user,
            event=past_event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )
        reg_past.confirm()
        reg_past.save()

        future_event = Event.objects.create(
            name="Future Event",
            program=self.program,
            starts_at=self.test_today_datetime_noon + datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon + datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon + datetime.timedelta(days=4)
        )
        reg_future = Registration.objects.create(
            user=self.user,
            event=future_event,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )
        reg_future.confirm()
        reg_future.save()

        statistics = self.service.fetch_user_statistics(self.user)

        self.assertEqual(statistics['total_events_attended'], 1)
        self.assertEqual(statistics['times_as_ride_leader'], 1)

    def test_fetch_user_statistics_only_counts_confirmed(self):
        past_event_1 = Event.objects.create(
            name="Past Event 1",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=10),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=11)
        )
        reg_confirmed = Registration.objects.create(
            user=self.user,
            event=past_event_1,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )
        reg_confirmed.confirm()
        reg_confirmed.save()

        past_event_2 = Event.objects.create(
            name="Past Event 2",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=5),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=6)
        )
        reg_submitted = Registration.objects.create(
            user=self.user,
            event=past_event_2,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )

        past_event_3 = Event.objects.create(
            name="Past Event 3",
            program=self.program,
            starts_at=self.test_today_datetime_noon - datetime.timedelta(days=3),
            ends_at=self.test_today_datetime_noon - datetime.timedelta(days=3),
            registration_closes_at=self.test_today_datetime_noon - datetime.timedelta(days=4)
        )
        reg_withdrawn = Registration.objects.create(
            user=self.user,
            event=past_event_3,
            name=self.user.username,
            email=self.user.email,
            state=Registration.STATE_SUBMITTED,
            ride_leader_preference=Registration.RideLeaderPreference.YES
        )
        reg_withdrawn.confirm()
        reg_withdrawn.withdraw()
        reg_withdrawn.save()

        statistics = self.service.fetch_user_statistics(self.user)

        self.assertEqual(statistics['total_events_attended'], 1)
        self.assertEqual(statistics['times_as_ride_leader'], 1)


class RegistrationTrackingTestCase(TestCase):
    def setUp(self):
        self.service = RegistrationService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        self.user.profile.phone = "+16131112222"
        self.user.profile.save()
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            program=self.program,
            name="Test Event",
            starts_at=timezone.now() + timezone.timedelta(days=7),
            registration_closes_at=timezone.now() + timezone.timedelta(days=6),
            requires_emergency_contact=False,
            ride_leaders_wanted=False
        )
        mail.outbox = []

    def test_registration_captures_ip_address(self):
        user_detail = UserDetail(
            first_name="Test",
            last_name="User",
            email=self.user.email,
            phone="+16131112222"
        )
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=None,
            speed_range_preference=None,
            emergency_contact_name=None,
            emergency_contact_phone=None
        )
        request_detail = RequestDetail(
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0',
            authenticated=True
        )

        self.service.register(user_detail, registration_detail, self.event, request_detail)

        registration = Registration.objects.get(user=self.user, event=self.event)
        self.assertEqual(registration.ip_address, '192.168.1.100')

    def test_registration_captures_user_agent(self):
        user_detail = UserDetail(
            first_name="Test",
            last_name="User",
            email=self.user.email,
            phone="+16131112222"
        )
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=None,
            speed_range_preference=None,
            emergency_contact_name=None,
            emergency_contact_phone=None
        )
        request_detail = RequestDetail(
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            authenticated=True
        )

        self.service.register(user_detail, registration_detail, self.event, request_detail)

        registration = Registration.objects.get(user=self.user, event=self.event)
        self.assertEqual(registration.user_agent, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    def test_registration_captures_authenticated_status_true(self):
        user_detail = UserDetail(
            first_name="Test",
            last_name="User",
            email=self.user.email,
            phone="+16131112222"
        )
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=None,
            speed_range_preference=None,
            emergency_contact_name=None,
            emergency_contact_phone=None
        )
        request_detail = RequestDetail(
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0',
            authenticated=True
        )

        self.service.register(user_detail, registration_detail, self.event, request_detail)

        registration = Registration.objects.get(user=self.user, event=self.event)
        self.assertTrue(registration.authenticated)

    def test_registration_captures_authenticated_status_false(self):
        new_user_email = 'newuser@example.com'
        user_detail = UserDetail(
            first_name="New",
            last_name="User",
            email=new_user_email,
            phone="+16131113333"
        )
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=None,
            speed_range_preference=None,
            emergency_contact_name=None,
            emergency_contact_phone=None
        )
        request_detail = RequestDetail(
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0',
            authenticated=False
        )

        self.service.register(user_detail, registration_detail, self.event, request_detail)

        registration = Registration.objects.get(email=new_user_email, event=self.event)
        self.assertFalse(registration.authenticated)

    def test_registration_without_request_detail_has_null_tracking_fields(self):
        user_detail = UserDetail(
            first_name="Test",
            last_name="User",
            email=self.user.email,
            phone="+16131112222"
        )
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=None,
            speed_range_preference=None,
            emergency_contact_name=None,
            emergency_contact_phone=None
        )

        self.service.register(user_detail, registration_detail, self.event)

        registration = Registration.objects.get(user=self.user, event=self.event)
        self.assertIsNone(registration.ip_address)
        self.assertIsNone(registration.user_agent)
        self.assertIsNone(registration.authenticated)