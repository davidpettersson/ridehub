# web/forms.py
from django import forms
from backoffice.models import Registration, Event, Ride, SpeedRange


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ['name', 'email']
        # Base fields only include name and email

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)

        if self.event:
            # Set event as a hidden field with initial value
            self.fields['event'] = forms.ModelChoiceField(
                queryset=Event.objects.filter(id=self.event.id),
                initial=Event.objects.get(id=self.event.id),
                widget=forms.HiddenInput(),
                required=True
            )

            # Only add ride and speed fields if this event has rides
            has_rides = Ride.objects.filter(event=self.event).exists()
            if has_rides:
                self.fields['ride'] = forms.ModelChoiceField(
                    queryset=Ride.objects.filter(event=self.event),
                    label="Select Ride",
                    required=True
                )

                self.fields['speed_range_preference'] = forms.ModelChoiceField(
                    queryset=SpeedRange.objects.all(),
                    label="Speed Range Preference",
                    required=False
                )

            # Add emergency contact fields only if required by the event
            if self.event.requires_emergency_contact:
                self.fields['emergency_contact_name'] = forms.CharField(
                    max_length=128,
                    label="Emergency Contact Name",
                    required=True
                )
                self.fields['emergency_contact_phone'] = forms.CharField(
                    max_length=128,
                    label="Emergency Contact Phone",
                    required=True
                )

            # Add ride leader preference field only if relevant for this event
            if self.event.ride_leaders_wanted and has_rides:
                self.fields['ride_leader_preference'] = forms.ChoiceField(
                    choices=[
                        (Registration.RIDE_LEADER_YES, 'Yes'),
                        (Registration.RIDE_LEADER_NO, 'No')
                    ],
                    label="Would you like to be a ride leader?",
                    widget=forms.RadioSelect(),
                    required=True
                )
            else:
                # Still set the default value in the instance but don't show in form
                self.instance.ride_leader_preference = Registration.RIDE_LEADER_NOT_APPLICABLE

        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select) and not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, (forms.HiddenInput, forms.RadioSelect)):
                field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.event = self.event

        # Check if this event has no rides, set ride to None
        has_rides = Ride.objects.filter(event=self.event).exists()
        if not has_rides:
            instance.ride = None
            instance.speed_range_preference = None
            instance.ride_leader_preference = Registration.RIDE_LEADER_NOT_APPLICABLE

        if commit:
            instance.save()

        return instance