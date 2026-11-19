from django.urls import path

from agents.views import llms_txt, poppy_manifest

urlpatterns = [
    path('llms.txt', llms_txt, name='llms_txt'),
    path('.well-known/poppy.json', poppy_manifest, name='poppy_manifest'),
]
