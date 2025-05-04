from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta

from backoffice.models import Registration


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """
    User profile view that shows all user registrations.
    """
    # Filter out events that started more than 24 hours ago
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    user_registrations = Registration.objects.filter(
        user=request.user,
        event__starts_at__gte=twenty_four_hours_ago
    ).order_by('event__starts_at')
    
    # Check if user is a ride leader for any event
    is_ride_leader = user_registrations.filter(
        state='confirmed',
        ride_leader_preference=Registration.RIDE_LEADER_YES,
        event__ride_leaders_wanted=True
    ).exists()
    
    context = {
        'registrations': user_registrations,
        'is_ride_leader': is_ride_leader
    }
    return render(request, 'web/profile/profile.html', context=context)


@login_required
def registration_withdraw(request: HttpRequest, registration_id: int) -> HttpResponseRedirect:
    """
    Withdraw a user's registration for an event.
    """
    registration = get_object_or_404(Registration, id=registration_id, user=request.user)
    
    if registration.state == 'confirmed' and request.method == 'POST':
        registration.withdraw()
        registration.save()
        
    return redirect('profile')