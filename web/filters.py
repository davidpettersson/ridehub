import django_filters
from django import forms
from django.db.models import Q

from backoffice.models import Registration, Ride


class RegistrationFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method='filter_search',
        label="Search",
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Name or email'}),
    )
    state = django_filters.ChoiceFilter(
        choices=Registration.STATE_CHOICES,
        label="State",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
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
        fields = ['state', 'ride', 'ride_leader_preference']

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event:
            self.filters['ride'].queryset = Ride.objects.filter(event=event)

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(email__icontains=value)
        )
