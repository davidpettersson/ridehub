import logging
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpRequest
from django.utils.timezone import now

from backoffice.models import Registration

logger = logging.getLogger(__name__)


@staff_member_required
def changes_email_addresses(request: HttpRequest) -> HttpResponse:
    # Get all users with staff status
    staff_users = User.objects.filter(is_staff=True).values_list('email', flat=True)

    # Get all users that have at least once signed up to be a ride leader in the last year
    one_year_ago = now() - timedelta(days=365)

    ride_leader_users = User.objects.filter(
        registration__ride_leader_preference=Registration.RideLeaderPreference.YES,
        registration__submitted_at__gte=one_year_ago,
    ).distinct().values_list('email', flat=True)

    # Combine and deduplicate email addresses
    all_emails = set(staff_users) | set(ride_leader_users)

    # Remove officials
    all_emails_except_officials = filter(lambda e: e.endswith('@ottawabicycleclub.ca'), all_emails)

    # Return comma-separated email addresses
    email_list = ','.join(sorted(all_emails_except_officials))
    return HttpResponse(email_list, content_type='text/plain')
