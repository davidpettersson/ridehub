import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest

from backoffice.models import Registration

logger = logging.getLogger(__name__)


@staff_member_required
def changes_email_addresses(request: HttpRequest) -> HttpResponse:
    # Get all users with staff status
    staff_users = User.objects.filter(is_staff=True).values_list('email', flat=True)

    # Get all users that have at least once signed up to be a ride leader
    ride_leader_users = User.objects.filter(
        registration__ride_leader_preference=Registration.RideLeaderPreference.YES
    ).distinct().values_list('email', flat=True)

    # Combine and deduplicate email addresses
    all_emails = set(staff_users) | set(ride_leader_users)

    # Return comma-separated email addresses
    email_list = ', '.join(sorted(all_emails))
    return HttpResponse(email_list, content_type='text/plain')
