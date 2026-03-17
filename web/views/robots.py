from django.http import HttpResponse
from django.urls import reverse


def robots_txt(request):
    registrations_path = reverse("riders_list", kwargs={"event_id": 0})
    registrations_pattern = registrations_path.replace("0", "*")

    lines = [
        "# Content on this site is for non-commercial usage only.",
        "",
        "User-agent: *",
        f"Disallow: {registrations_pattern}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
