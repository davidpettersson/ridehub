from datetime import timedelta

from behave import *
from django.utils import timezone
from django.template.defaultfilters import date as date_filter

from backoffice.models import Event, Program, Registration
from backoffice.services.registration_service import RegistrationService, RegistrationDetail
from backoffice.services.user_service import UserDetail

use_step_matcher("parse")

TEST_EVENT_NAME_TOKEN = 'a39c40cd-f33c-424f-af8c-23703d39c319'


@given("an event")
def given_an_event(context):
    now = timezone.now()

    program = Program.objects.create(
        name='Test program'
    )

    event = Event.objects.create(
        program=program,
        name=f"Test event {TEST_EVENT_NAME_TOKEN}",
        description='Test description',
        starts_at=now + timedelta(days=3),
        registration_closes_at=now + timedelta(days=2),
    )

    context.scenario_objects['program'] = program
    context.scenario_objects['event'] = event


@step("the event has external registration")
def step_impl(context):
    context.scenario_objects['event'].external_registration_url = 'https://www.sunet.se'
    context.scenario_objects['event'].save()


@step("the event registration limit is {limit:w}")
def set_registration_limit(context, limit: str):
    match limit:
        case 'empty':
            context.scenario_objects['event'].registration_limit = None
        case _:
            context.scenario_objects['event'].registration_limit = int(limit)
    context.scenario_objects['event'].save()


@when("visiting the event detail page")
def step_impl(context):
    context.scenario_objects['response'] = context.test.client.get(f"/events/{context.scenario_objects['event'].id}")
    context.test.assertEqual(200, context.scenario_objects['response'].status_code)


@then('the event shows {count:d} registered')
def step_impl(context, count):
    context.test.assertContains(context.scenario_objects['response'], f"{count} registered")


@then('the event shows {count:d} registration remaining')
@then('the event shows {count:d} registrations remaining')
def step_impl(context, count):
    context.test.assertContains(context.scenario_objects['response'], f"{count} remaining")


@step("the event has {count:d} registration")
def step_impl(context, count):
    rs = RegistrationService()
    for k in range(count):
        email = f"john-{k}@doe.com"
        user_detail = UserDetail(
            first_name=f'John {k}',
            last_name='Doe',
            email=email,
            phone='',
        )
        registration_detail = RegistrationDetail(
            ride=None,
            ride_leader_preference=Registration.RideLeaderPreference.NOT_APPLICABLE,
            speed_range_preference=None,
            emergency_contact_name='',
            emergency_contact_phone=''
        )
        rs.register(user_detail, registration_detail, context.scenario_objects['event'])
    context.test.assertEqual(count, context.scenario_objects['event'].registration_count)


@then("the event does not show registrations remaining")
def step_impl(context):
    context.test.assertNotContains(context.scenario_objects['response'], f"remaining")


@step("the event does not show registrations")
def step_impl(context):
    context.test.assertNotContains(context.scenario_objects['response'], f"registered")


@when("visiting the event ical feed")
def step_impl(context):
    context.scenario_objects['response'] = context.test.client.get(f"/events.ics")
    context.test.assertEqual(200, context.scenario_objects['response'].status_code)


@then("the event ical feed contains the event")
def step_impl(context):
    context.test.assertContains(context.scenario_objects['response'], TEST_EVENT_NAME_TOKEN)


@step("the event shows it is fully registered")
def step_impl(context):
    context.test.assertContains(context.scenario_objects['response'], "(full)")


@then("the event shows when registration closes")
def step_impl(context):
    close_at = context.scenario_objects['event'].registration_closes_at.astimezone(timezone.get_current_timezone())
    formatted_close_at = date_filter(close_at, "F j, g:i A")
    needle = f"Registration closes {formatted_close_at}"
    context.test.assertContains(context.scenario_objects['response'], needle)
