from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from waffle import flag_is_active

from backoffice.models import Registration, UserProfile
from backoffice.services.membership_service import MembershipService
from backoffice.services.registration_service import RegistrationService
from backoffice.services.user_service import UserService
from web.forms import MembershipNumberForm, NameVisibilityForm


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    registration_service = RegistrationService()
    registrations = registration_service.fetch_current_registrations(request.user)
    past_registrations = registration_service.fetch_past_registrations(request.user)

    context = {
        'registrations': registrations,
        'past_registrations': past_registrations,
        'name_visibility': request.user.profile.name_visibility,
        'name_visibility_choices': UserProfile.NameVisibility.choices,
        'registration_visibility_hours': settings.REGISTRATION_VISIBILITY_HOURS,
    }

    if flag_is_active(request, 'capture_membership_number'):
        membership_service = MembershipService()
        membership_number = membership_service.get_current_membership_number(request.user)
        context['membership_number'] = membership_number

    return render(request, 'web/profile/profile.html', context=context)


@login_required
def registration_withdraw(request: HttpRequest, registration_id: int) -> HttpResponseRedirect:
    registration = get_object_or_404(Registration, id=registration_id, user=request.user)

    if registration.state == 'confirmed' and request.method == 'POST':
        registration.withdraw()
        registration.save()

    return redirect('profile')


@login_required
def profile_name_visibility(request: HttpRequest) -> HttpResponseRedirect:
    if request.method == 'POST':
        form = NameVisibilityForm(request.POST)
        if form.is_valid():
            UserService().update_name_visibility(request.user, form.cleaned_data['name_visibility'])

    return redirect('profile')


@login_required
def profile_membership_number(request: HttpRequest) -> HttpResponseRedirect:
    if request.method == 'POST' and flag_is_active(request, 'capture_membership_number'):
        form = MembershipNumberForm(request.POST)
        membership_service = MembershipService()
        if form.is_valid() and not membership_service.has_current_membership_number(request.user):
            membership_service.save_membership_number(request.user, form.cleaned_data['membership_number'])

    return redirect('profile')
