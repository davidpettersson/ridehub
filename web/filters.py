import django_filters
from django import forms
from django.db.models import Q

from backoffice.models import Registration, Ride, SpeedRange


class BaseRegistrationFilter(django_filters.FilterSet):
    ride = django_filters.ModelChoiceFilter(
        queryset=Ride.objects.none(),
        label="Ride",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    ride_leader_preference = django_filters.ChoiceFilter(
        choices=Registration.RideLeaderPreference.choices,
        label="Ride leader",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    class Meta:
        model = Registration
        fields = ['ride', 'ride_leader_preference']

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event:
            self.filters['ride'].queryset = Ride.objects.filter(event=event)


class RegistrationFilter(BaseRegistrationFilter):
    search = django_filters.CharFilter(
        method='filter_search',
        label="Search",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Name or email'}),
    )

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(email__icontains=value)
        )


class PublicRegistrationFilter(BaseRegistrationFilter):
    speed_range_preference = django_filters.ModelChoiceFilter(
        queryset=SpeedRange.objects.none(),
        label="Speed",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, event=event, **kwargs)
        if event:
            self.filters['speed_range_preference'].queryset = (
                SpeedRange.objects.filter(ride__event=event).distinct()
            )
