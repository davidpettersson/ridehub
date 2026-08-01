from copy import copy

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_fsm import TransitionNotAllowed

from .models import Event
from .widgets import EndsAtWidget, RegistrationClosesAtWidget


class EventDuplicationForm(forms.Form):
    event_id = forms.IntegerField(widget=forms.HiddenInput())
    new_name = forms.CharField(max_length=128, label="New Event Name")
    new_date = forms.DateField(
        widget=forms.DateInput(
            attrs={'type': 'date'},
            format='%Y-%m-%d'
        ),
        input_formats=['%Y-%m-%d'],
        label="New Date"
    )


EventDuplicationFormSet = forms.formset_factory(EventDuplicationForm, extra=0)


class EventRescheduleForm(forms.Form):
    starts_at = forms.DateTimeField(
        label='New start',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
    )
    ends_at = forms.DateTimeField(
        label='New end',
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        help_text='Leave blank to assume a one hour event.',
    )
    registration_closes_at = forms.DateTimeField(
        label='Registration closes',
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        help_text='Must be at or before the new start time.',
    )
    reschedule_reason = forms.CharField(
        label='Reason for rescheduling',
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 80}),
        help_text='Shown on the event page and included in the notification email.',
    )
    notify_registrants = forms.BooleanField(
        label='Notify confirmed registrants by email',
        required=False,
        initial=True,
    )

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def clean_reschedule_reason(self):
        return self.cleaned_data['reschedule_reason'].strip()

    def clean(self):
        cleaned_data = super().clean()

        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')
        registration_closes_at = cleaned_data.get('registration_closes_at')

        if starts_at and starts_at <= timezone.now():
            self.add_error('starts_at', 'A rescheduled event cannot start in the past.')
            return cleaned_data

        if starts_at and self.event and self._same_minute(starts_at, self.event.starts_at):
            self.add_error('starts_at', 'The new start time must differ from the current start time.')
            return cleaned_data

        if starts_at and self.event:
            candidate = copy(self.event)
            candidate.starts_at = starts_at
            candidate.ends_at = ends_at
            candidate.registration_closes_at = registration_closes_at
            candidate.reschedule_reason = cleaned_data.get('reschedule_reason', '')
            candidate.previous_starts_at = self.event.starts_at
            candidate.rescheduled_at = timezone.now()

            try:
                candidate.clean()
            except ValidationError as error:
                self._add_model_errors(error)

        return cleaned_data

    @staticmethod
    def _same_minute(left, right):
        return left.replace(second=0, microsecond=0) == right.replace(second=0, microsecond=0)

    def _add_model_errors(self, error: ValidationError):
        for field, messages in error.message_dict.items():
            target = field if field in self.fields else None
            for message in messages:
                self.add_error(target, message)


class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = '__all__'
        widgets = {
            'ends_at': EndsAtWidget(),
            'registration_closes_at': RegistrationClosesAtWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.instance._original_state = self.instance.state
        else:
            self.instance._original_state = None
        if 'ends_at' in self.fields:
            self.fields['ends_at'].required = False
        if 'state' in self.fields:
            self.fields['state'].choices = [
                (value, label)
                for value, label in self.fields['state'].choices
                if value not in (Event.STATE_CANCELLED, Event.STATE_ARCHIVED)
            ]

    def _find_transition_method(self, old_state, new_state):
        for t in self.instance.get_all_state_transitions():
            if t.source == old_state and t.target == new_state:
                return t.name
        return None

    def clean(self):
        cleaned_data = super().clean()
        if not (self.instance.pk and self.instance._original_state):
            return cleaned_data

        old_state = self.instance._original_state
        new_state = cleaned_data.get('state', old_state)

        if old_state == new_state:
            return cleaned_data

        self.instance.state = old_state

        method_name = self._find_transition_method(old_state, new_state)
        if method_name is None:
            raise ValidationError(
                f"Cannot change state from '{old_state}' to '{new_state}'. "
                f"This transition is not supported."
            )

        method = getattr(self.instance, method_name)
        try:
            method()
        except TransitionNotAllowed:
            raise ValidationError(
                f"Cannot change state from '{old_state}' to '{new_state}'. "
                f"The event may have confirmed registrations that prevent this change."
            )

        self.instance.state = old_state
        self._transition_method_name = method_name

        return cleaned_data

    def save(self, commit=True):
        if hasattr(self, '_transition_method_name'):
            self.instance.state = self.instance._original_state
            method = getattr(self.instance, self._transition_method_name)
            method()

        return super().save(commit=commit)