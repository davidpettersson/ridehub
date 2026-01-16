from django import forms

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
        # Make ends_at not required at the form level, 
        # as the model allows it to be blank/null and our widget facilitates setting it.
        # The model's blank=True, null=True already handles DB level optionality.
        if 'ends_at' in self.fields:
            self.fields['ends_at'].required = False 