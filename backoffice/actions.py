from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.shortcuts import render, redirect
from django.template.response import TemplateResponse
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

from backoffice.services import EmailService
from backoffice.models import Registration


def cancel_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    """
    Admin action to cancel events and notify registered users.
    
    This action will:
    1. Mark each event as cancelled
    2. Record the cancellation time and reason
    3. Send email notifications to registered users who haven't withdrawn
    """
    # Handle the cancellation form submission
    if request.method == 'POST' and 'post' in request.POST:
        cancellation_reason = request.POST.get('cancellation_reason', '')
        now = timezone.now()
        
        # Update each event
        cancel_count = 0
        for event in query_set:
            event.cancelled = True
            event.cancelled_at = now
            event.cancellation_reason = cancellation_reason
            event.save()
            
            # Send notification emails to confirmed registrations
            for registration in event.registration_set.filter(state=Registration.STATE_CONFIRMED):
                # Don't send notifications to withdrawn registrations
                context = {
                    'event': event,
                    'registration': registration,
                    'cancellation_reason': cancellation_reason,
                    'base_url': f"https://{request.get_host()}"
                }
                
                EmailService.send_email(
                    template_name='event_cancelled',
                    context=context,
                    subject=f"CANCELLED: {event.name}",
                    recipient_list=[registration.email],
                )
            
            cancel_count += 1
        
        if cancel_count == 1:
            message = "1 event was successfully cancelled and notifications were sent."
        else:
            message = f"{cancel_count} events were successfully cancelled and notifications were sent."
        
        admin.message_user(request, message, messages.SUCCESS)
        return redirect('admin:backoffice_event_changelist')
        
    # Display a confirmation form to enter the cancellation reason
    context = {
        'title': 'Cancel selected events',
        'queryset': query_set,
        'opts': admin.model._meta,
        'action_checkbox_name': ACTION_CHECKBOX_NAME,
    }
    
    return TemplateResponse(request, 'admin/backoffice/event/cancel_selected_confirmation.html', context)


cancel_event.short_description = "Cancel selected events"


def duplicate_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    duplicate_count = 0

    if duplicate_count == 1:
        message = "1 event was successfully cancelled."
    else:
        message = f"{duplicate_count} events were successfully cancelled."

    admin.message_user(request, message, messages.SUCCESS)


duplicate_event.short_description = "Duplicate selected events (does not work yet)"

def archive_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    archive_count = 0
    now = timezone.now()

    for event in query_set:
        event.archived = True
        event.archived_at = now
        event.save()

        archive_count += 1

    if archive_count == 1:
        message = "1 event was successfully archived."
    else:
        message = f"{archive_count} events were successfully archived."

    admin.message_user(request, message, messages.SUCCESS)

archive_event.short_description = "Archive selected events"
