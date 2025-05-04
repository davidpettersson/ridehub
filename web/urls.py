from django.urls import path
from sesame.views import LoginView

from web.views.debug import trigger_task
from web.views.events import redirect_to_event_list, event_detail, event_list, event_riders
from web.views.login import LoginFormView, logout_view
from web.views.registrations import registration_create, registration_detail, registration_submitted, registration_list, \
    get_speed_ranges
from web.views.profile import profile, registration_withdraw

urlpatterns = [
    path("login/", LoginFormView.as_view(), name="login_form"),
    path("login/auth/", LoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    path('debug/trigger_task', trigger_task),
    path('calendar', redirect_to_event_list, name='calendar'),
    path('events/<int:event_id>/riders', event_riders, name='riders_list'),
    path('events/<int:event_id>/registration', registration_create, name='registration_create'),
    path('events/<int:event_id>', event_detail, name='event_detail'),
    path('events', event_list, name='event_list'),
    path('registrations/<int:registration_id>/withdraw', registration_withdraw, name='registration_withdraw'),
    path('registrations/<int:registration_id>', registration_detail, name='registration_detail'),
    path('registrations/submitted', registration_submitted, name='registration_submitted'),
    path('registrations', registration_list, name='registration_list'),
    path('rides/<int:ride_id>/speed-ranges', get_speed_ranges, name='get_speed_ranges'),
    path('profile', profile, name='profile'),
    path('', redirect_to_event_list, name='index'),
]
