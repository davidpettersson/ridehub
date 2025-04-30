from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse

from backoffice.models import Registration


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """
    User profile view that shows all user registrations.
    """
    user_registrations = Registration.objects.filter(user=request.user).order_by('event__starts_at')
    
    context = {
        'registrations': user_registrations,
    }
    return render(request, 'web/profile/profile.html', context=context)


@login_required
def registration_withdraw(request: HttpRequest, registration_id: int) -> HttpResponseRedirect:
    """
    Withdraw a user's registration for an event.
    """
    registration = get_object_or_404(Registration, id=registration_id, user=request.user)
    
    if registration.state == 'confirmed' and request.method == 'POST':
        registration.cancel()
        registration.save()
        
    return redirect('profile') 