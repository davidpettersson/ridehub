from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect

from backoffice.models import Registration
from backoffice.services.registration_service import RegistrationService


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    registration_service = RegistrationService()
    registrations = registration_service.fetch_current_registrations(request.user)
    past_registrations = registration_service.fetch_past_registrations(request.user)
    statistics = registration_service.fetch_user_statistics(request.user)

    context = {
        'registrations': registrations,
        'past_registrations': past_registrations,
        'statistics': statistics,
    }

    return render(request, 'web/profile/profile.html', context=context)


@login_required
def registration_withdraw(request: HttpRequest, registration_id: int) -> HttpResponseRedirect:
    registration = get_object_or_404(Registration, id=registration_id, user=request.user)

    if registration.state == 'confirmed' and request.method == 'POST':
        registration.withdraw()
        registration.save()

    return redirect('profile')
