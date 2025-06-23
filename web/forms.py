from django import forms

from backoffice.models import Registration, Event, Ride, SpeedRange


class RegistrationForm(forms.Form):
    name = forms.CharField(max_length=128, required=True, min_length=2, widget=forms.TextInput(attrs={
        'autocomplete': 'name'
    }))
    email = forms.EmailField(max_length=128, required=True, widget=forms.EmailInput(attrs={
        'autocomplete': 'email'
    }))

    def __init__(self, *args, **kwargs):
        event: Event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        assert event

        # Only add ride and speed fields if this event has rides
        if Ride.objects.filter(event=event).exists():
            self.fields['ride'] = forms.ModelChoiceField(
                queryset=Ride.objects.filter(event=event),
                label="Ride",
                required=True
            )

            self.fields['speed_range_preference'] = forms.ModelChoiceField(
                queryset=SpeedRange.objects.all(),
                label="Speed range preference",
                required=True
            )

        if event.requires_emergency_contact:
            self.fields['emergency_contact_name'] = forms.CharField(
                max_length=128,
                min_length=2,
                label="Emergency contact name",
                required=True,
                widget=forms.TextInput(attrs={
                    'autocomplete': 'off'
                })
            )
            self.fields['emergency_contact_phone'] = forms.CharField(
                max_length=128,
                min_length=2,
                label="Emergency contact phone",
                required=True,
                widget=forms.TextInput(attrs={
                    'type': 'tel',
                    'autocomplete': 'off'
                })
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

        if event.requires_membership:
            self.fields['membership_confirmation'] = forms.BooleanField(
                required=True,
                label="I am a current OBC member",
                error_messages={
                    'required': 'You must confirm that you are a current OBC member to register for this event.'
                }
            )

        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select) and not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, (forms.HiddenInput, forms.RadioSelect, forms.CheckboxInput)):
                field.widget.attrs['class'] = 'form-control'


class EmailLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'autocomplete': 'email'
    }))
