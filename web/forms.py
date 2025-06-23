from django import forms
from backoffice.models import Registration, Event, Ride, SpeedRange


class RegistrationForm(forms.Form):
    name = forms.CharField(max_length=128, required=True, min_length=2)
    email = forms.EmailField(max_length=128, required=True)

    def __init__(self, *args, **kwargs):
        event: Event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        assert event
        import pprint
        pprint.pprint(f"e={event}")
        # Only add ride and speed fields if this event has rides
        if Ride.objects.filter(event=event).exists():
            self.fields['ride'] = forms.ModelChoiceField(
                queryset=Ride.objects.filter(event=event),
                label="Ride",
                required=True
            )

            self.fields['speed_range_preference'] = forms.ModelChoiceField(
                queryset=SpeedRange.objects.all(),
                label="Speed Range Preference",
                required=True
            )

        if event.requires_emergency_contact:
            self.fields['emergency_contact_name'] = forms.CharField(
                max_length=128,
                min_length=2,
                label="Emergency Contact Name",
                required=True
            )
            self.fields['emergency_contact_phone'] = forms.CharField(
                max_length=128,
                min_length=2,
                label="Emergency Contact Phone",
                required=True
            )

        if event.ride_leaders_wanted:
            self.fields['ride_leader_preference'] = forms.ChoiceField(
                choices=[
                    (Registration.RideLeaderPreference.YES, 'Yes'),
                    (Registration.RideLeaderPreference.NO, 'No')
                ],
                label="Would you like to be a ride leader?",
                widget=forms.RadioSelect(),
                required=True
            )

        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select) and not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, (forms.HiddenInput, forms.RadioSelect)):
                field.widget.attrs['class'] = 'form-control'


class EmailLoginForm(forms.Form):
    email = forms.EmailField()