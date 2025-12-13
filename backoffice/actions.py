from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

from backoffice.services.email_service import EmailService
from backoffice.services.event_service import EventService
from backoffice.models import Registration
from backoffice.forms import EventDuplicationFormSet


def cancel_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    if request.method == 'POST' and 'post' in request.POST:
        cancellation_reason = request.POST.get('cancellation_reason', '')
        now = timezone.now()
        
        cancel_count = 0
        for event in query_set:
            event.cancelled = True
            event.cancelled_at = now
            event.cancellation_reason = cancellation_reason
            event.save()
            
            for registration in event.registration_set.filter(state=Registration.STATE_CONFIRMED):
                context = {
                    'event': event,
                    'registration': registration,
                    'cancellation_reason': cancellation_reason,
                    'base_url': f"https://{request.get_host()}"
                }
                
                EmailService().send_email(
                    template_name='event_cancelled',
                    context=context,
                    subject=f"RIDE CANCELLED {event.name}",
                    recipient_list=[registration.email],
                )
            
            cancel_count += 1
        
        if cancel_count == 1:
            message = "1 event was successfully cancelled and notifications were sent."
        else:
            message = f"{cancel_count} events were successfully cancelled and notifications were sent."
        
        admin.message_user(request, message, messages.SUCCESS)
        return redirect('admin:backoffice_event_changelist')
        
    context = {
        'title': 'Cancel selected events',
        'queryset': query_set,
        'opts': admin.model._meta,
        'action_checkbox_name': ACTION_CHECKBOX_NAME,
    }
    
    return TemplateResponse(request, 'admin/backoffice/event/cancel_selected_confirmation.html', context)


cancel_event.short_description = "Cancel selected events"


def duplicate_event(admin: ModelAdmin, request: HttpRequest, query_set: QuerySet):
    if request.method == 'POST' and 'post' in request.POST:
        formset = EventDuplicationFormSet(request.POST)

        if formset.is_valid():
            service = EventService()
            duplicate_count = 0

            events_by_id = {event.pk: event for event in query_set}

            for form in formset:
                event_id = form.cleaned_data['event_id']
                new_name = form.cleaned_data['new_name']
                new_starts_at = form.cleaned_data['new_starts_at']

                source_event = events_by_id.get(event_id)
                if source_event:
                    service.duplicate_event(source_event, new_name, new_starts_at)
                    duplicate_count += 1

            if duplicate_count == 1:
                message = "1 event was successfully duplicated."
            else:
                message = f"{duplicate_count} events were successfully duplicated."

            admin.message_user(request, message, messages.SUCCESS)
            return redirect('admin:backoffice_event_changelist')

    events_list = list(query_set)
    initial_data = [
        {
            'event_id': event.pk,
            'new_name': event.name,
            'new_starts_at': event.starts_at.strftime('%Y-%m-%dT%H:%M'),
        }
        for event in events_list
    ]
    formset = EventDuplicationFormSet(initial=initial_data)
    forms_with_events = list(zip(formset, events_list))

    context = {
        'title': 'Duplicate selected events',
        'queryset': query_set,
        'opts': admin.model._meta,
        'action_checkbox_name': ACTION_CHECKBOX_NAME,
        'formset': formset,
        'forms_with_events': forms_with_events,
    }

    return TemplateResponse(request, 'admin/backoffice/event/duplicate_selected.html', context)


duplicate_event.short_description = "Duplicate selected events"

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
