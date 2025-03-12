"""
URL configuration for ridehub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path, include

from web import views

urlpatterns = [
    path('calendar', views.calendar, name='calendar'),
    path('events/<int:event_id>/register', views.registration_create, name='registration_create'),
    path('events/<int:event_id>', views.event_detail, name='event_detail'),
    path('events', views.event_list, name='event_list'),
    path('registrations/<int:registration_id>', views.registration_detail, name='registration_detail'),
    path('registrations', views.registration_list, name='registration_list'),
]
