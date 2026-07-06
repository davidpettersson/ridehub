from django.urls import path

from agents.views import llms_txt

urlpatterns = [
    path('llms.txt', llms_txt, name='llms_txt'),
]
