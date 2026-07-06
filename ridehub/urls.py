from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('markdownx/', include('markdownx.urls')),
    path('', include('agents.urls')),
    path('', include('web.urls')),
]
