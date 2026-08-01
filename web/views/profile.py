import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from waffle import flag_is_active

from backoffice.models import Registration, UserProfile
from backoffice.services.membership_service import MembershipService
from backoffice.services.registration_service import RegistrationService, NAME_MASKING_STRATEGY
from backoffice.services.user_service import UserService
from web.forms import MembershipNumberForm, NameVisibilityForm

logger = logging.getLogger(__name__)


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    registration_service = RegistrationService()
    registrations = registration_service.mark_withdrawable(
        registration_service.mark_editable(
            list(registration_service.fetch_current_registrations(request.user))
        )
    )
    past_registrations = registration_service.fetch_past_registrations(request.user)

    masked_first_name, masked_last_name = NAME_MASKING_STRATEGY(request.user)

    context = {
        'registrations': registrations,
        'past_registrations': past_registrations,
        'name_visibility': request.user.profile.name_visibility,
        'name_visibility_choices': UserProfile.NameVisibility.choices,
        'registration_visibility_hours': settings.REGISTRATION_VISIBILITY_HOURS,
        'masked_name_example': f'{masked_first_name} {masked_last_name}',
    }

    if flag_is_active(request, 'capture_membership_number'):
        membership_service = MembershipService()
        membership_number = membership_service.get_current_membership_number(request.user)
        context['membership_number'] = membership_number

    return render(request, 'web/profile/profile.html', context=context)


@login_required
def registration_withdraw(request: HttpRequest, registration_id: int) -> HttpResponseRedirect:
    registration = get_object_or_404(
        Registration.objects.select_related('event'), id=registration_id, user=request.user)

    registration_service = RegistrationService()
    allowed, reason = registration_service.is_registration_withdrawable(registration)

    if request.method == 'POST':
        if not allowed:
            logger.warning(
                "Registration withdrawal not allowed",
                extra={'registration': registration.id, 'reason': reason},
            )
        else:
            registration_service.withdraw_registration(registration, request.user)

    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)

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
