from django import forms
from .models import Event
from .widgets import EndsAtWidget, RegistrationClosesAtWidget

class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = '__all__' # Or list specific fields if you don't want all of them
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