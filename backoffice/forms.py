from django import forms
from django.core.exceptions import ValidationError
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