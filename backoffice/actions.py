from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest


def cancel_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    cancel_count = 0

    if cancel_count == 1:
        message = "1 event was successfully cancelled."
    else:
        message = f"{cancel_count} events were successfully cancelled."

    admin.message_user(request, message, messages.SUCCESS)


cancel_event.short_description = "Cancel selected events (does not work yet)"


def duplicate_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    duplicate_count = 0

    if duplicate_count == 1:
        message = "1 event was successfully cancelled."
    else:
        message = f"{duplicate_count} events were successfully cancelled."

    admin.message_user(request, message, messages.SUCCESS)


duplicate_event.short_description = "Duplicate selected events (does not work yet)"
