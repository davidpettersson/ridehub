from django import forms

from .models import Event
from .widgets import EndsAtWidget, RegistrationClosesAtWidget


class EventDuplicationForm(forms.Form):
    event_id = forms.IntegerField(widget=forms.HiddenInput())
    new_name = forms.CharField(max_length=128, label="New Event Name")
    new_starts_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M'
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        label="New Start Time"
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
        # Make ends_at not required at the form level, 
        # as the model allows it to be blank/null and our widget facilitates setting it.
        # The model's blank=True, null=True already handles DB level optionality.
        if 'ends_at' in self.fields:
            self.fields['ends_at'].required = False 