from django.urls import path

from web.views.events import event_detail, event_list, event_registrations, \
    event_registrations_full, calendar_view, events_redirect
from web.views.events_ical import EventFeed
from web.views.helpers import changes_email_addresses
from web.views.login import LoginFormView, logout_view, CustomLoginView
from web.views.profile import profile, registration_withdraw, profile_membership_number
from web.views.registrations import registration_create, registration_submitted, membership_number_capture
from web.views.rides import ride_speed_ranges
from web.views.reviews import review_2025
from web.views.robots import robots_txt

urlpatterns = [
    path("login/", LoginFormView.as_view(), name="login_form"),
    path("login/auth/", CustomLoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path('helpers/changes_email_addresses', changes_email_addresses),
    path('calendar', calendar_view, name='calendar'),
    path('calendar/<int:year>/<int:month>', calendar_view, name='calendar_month'),
    path('upcoming', event_list, name='upcoming'),
    path('events', events_redirect, name='events'),
    path('events/<int:event_id>/registrations/full', event_registrations_full, name='event_registrations_full'),
    path('events/<int:event_id>/registrations', event_registrations, name='riders_list'),
    path('events/<int:event_id>/registration', registration_create, name='registration_create'),
    path('events/<int:event_id>', event_detail, name='event_detail'),
    path('events.ics', EventFeed(), name='event_feed'),
    path('registrations/<int:registration_id>/withdraw', registration_withdraw, name='registration_withdraw'),
    path('registrations/submitted', registration_submitted, name='registration_submitted'),
    path('rides/<int:ride_id>/speed-ranges', ride_speed_ranges, name='get_speed_ranges'),
    path('events/<int:event_id>/membership-number', membership_number_capture, name='membership_number_capture'),
    path('profile', profile, name='profile'),
    path('profile/membership-number', profile_membership_number, name='profile_membership_number'),
    path('reviews/2025', review_2025, name='review_2025'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('', events_redirect, name='index'),
]
