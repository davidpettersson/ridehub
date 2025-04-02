from django.urls import path

from web import views

urlpatterns = [
    path('debug/trigger_task', views.trigger_task),
    path('calendar', views.redirect_to_event_list, name='calendar'),
    path('events/<int:event_id>/registration', views.registration_create, name='registration_create'),
    path('events/<int:event_id>', views.event_detail, name='event_detail'),
    path('events', views.event_list, name='event_list'),
    path('registrations/<int:registration_id>', views.registration_detail, name='registration_detail'),
    path('registrations/submitted', views.registration_submitted, name='registration_submitted'),
    path('registrations', views.registration_list, name='registration_list'),
    path('rides/<int:ride_id>/speed-ranges', views.get_speed_ranges, name='get_speed_ranges'),
    path('', views.redirect_to_event_list, name='index'),
]
