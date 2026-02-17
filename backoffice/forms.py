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

    def save(self, commit=True):
        if self.instance.pk and self.instance._original_state:
            old_state = self.instance._original_state
            new_state = self.cleaned_data.get('state', old_state)

            if old_state != new_state:
                self.instance.state = old_state

                method_name = None
                for t in self.instance.get_all_state_transitions():
                    if t.source == old_state and t.target == new_state:
                        method_name = t.name
                        break

                if method_name is None:
                    raise ValidationError(
                        f"Invalid state transition from {old_state} to {new_state}."
                    )

                method = getattr(self.instance, method_name)
                try:
                    method()
                except TransitionNotAllowed:
                    raise ValidationError(
                        f"Cannot move to {new_state}: transition is not allowed "
                        f"(event may have confirmed registrations)."
                    )

        return super().save(commit=commit)