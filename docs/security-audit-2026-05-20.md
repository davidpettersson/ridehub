# Security Audit — 2026-05-20

This document records the findings of a manual security review of the RideHub
codebase performed against the `main` branch on 2026-05-20. Each finding lists
the location, an explanation of the issue, an exploitation scenario, and a
suggested remediation. Severity is a rough judgement of impact × ease of
exploitation, not a CVSS score.

A finding being listed here means the reviewer thinks it deserves a closer
look — it does not necessarily mean it is exploitable in production today.
Several issues compound (e.g. issues 1 + 2 + 4 are an effective account
takeover chain), so the priority order roughly reflects that compound risk.

---

## 1. (CRITICAL) Host header injection in magic-link login → account takeover

**Where**

- `web/views/login.py:33` — `link = self.request.build_absolute_uri(link)`
- `web/views/login.py:39` — `base_url = self.request.build_absolute_uri('/').rstrip('/')`
- `ridehub/settings.py:22` — `ALLOWED_HOSTS = ["*"]`
- `ridehub/settings.py:84` — `SESAME_ONE_TIME = os.environ.get('SESAME_ONE_TIME') is not None`

**Issue**

The passwordless login flow constructs the magic link by calling
`request.build_absolute_uri(...)`, which uses `request.get_host()` —
i.e. whatever value the client supplies in the `Host` header. Django's
normal protection against this is `ALLOWED_HOSTS`, but in production
that is set to `["*"]`, so the `Host` header is accepted unchecked.

The link is rendered in the login email as both a clickable anchor and
copy-pasteable text:

```html
<p><a href="{{ login_link }}" class="button">Click here to log in</a></p>
...
<code>{{ login_link }}</code>
```

so it really is the host the victim's browser will hit when they click.

**Exploitation**

1. Attacker sends `POST /login/` with form field `email=victim@example.com`
   and HTTP header `Host: attacker.example`.
2. Server sends an email to `victim@example.com` containing
   `https://attacker.example/login/auth/?sesame=<TOKEN>`.
3. Victim clicks the link, expecting to log in. Their browser sends the
   sesame token (valid for 5 minutes) to `attacker.example`.
4. Attacker replays the token against the real domain
   (`https://obcrides.ca/login/auth/?sesame=<TOKEN>`) and is logged in
   as the victim.

The amplifier is finding #2: `SESAME_ONE_TIME` is set from
`os.environ.get('SESAME_ONE_TIME') is not None`. Unless that env var is
*actually set* in production, tokens are reusable for the full 5 minutes,
giving the attacker plenty of time to replay.

This requires no authentication, no XSS, and no social engineering beyond
"victim clicks an obvious login link they just requested." It is
indistinguishable from a normal phishing-resistant login flow from the
victim's perspective.

**Remediation**

1. Set `ALLOWED_HOSTS` to a hard-coded list (`["obcrides.ca",
   "www.obcrides.ca"]`) — this alone is enough to neutralise the attack,
   since Django will reject the spoofed `Host` header with a 400.
2. Independently, construct the login URL from `settings.WEB_HOST`
   instead of `request.build_absolute_uri()`, the way the verification
   and confirmation emails already do
   (`backoffice/services/registration_service.py:93`, `117`). This is
   defence in depth and removes the implicit dependency on
   `ALLOWED_HOSTS`.
3. Fix `SESAME_ONE_TIME` so it actually defaults to `True` in production
   (or make it unconditional). The current `is not None` check means
   the env var has to be *present* — any value works — and most
   deployments will not set an unfamiliar env var.

---

## 2. (HIGH) Any authenticated user can register arbitrary other users and overwrite their profile

**Where**

- `backoffice/services/registration_service.py:104-110` — `_should_skip_verification`
- `backoffice/services/user_service.py:31-69` — `find_by_email_or_create`
- `web/views/registrations.py:96-124` — `registration_create`

**Issue**

The registration form is open to authenticated and unauthenticated users
alike. The submitted `email`, `first_name`, `last_name`, and `phone`
are taken from the form, not from the logged-in user's account:

```python
user_detail = _get_user_details(form)
result = registration_service.register(
    user_detail=user_detail,
    ...
    request_detail=request_detail,
)
```

In `RegistrationService.register`, the user is looked up (or created) by
that submitted email:

```python
user = self.user_service.find_by_email_or_create(user_detail)
```

`find_by_email_or_create` silently overwrites first/last/phone on any
existing user matching that email, and (for non-staff users) calls
`set_unusable_password()` — clobbering whatever password might be set:

```python
case Some(user):
    if not user.is_staff:
        user.set_unusable_password()
    user.first_name = user_detail.first_name
    user.last_name  = user_detail.last_name
    user.save()
    user.profile.phone = user_detail.phone
    ...
```

Then `_should_skip_verification` is checked against
`request_detail.authenticated` — i.e. whether the *request* was
authenticated, regardless of whether the *user being registered* is the
same person:

```python
def _should_skip_verification(self, user, request_detail):
    if request_detail and request_detail.authenticated:
        if not user.profile.email_verified:
            user.profile.email_verified = True
            user.profile.save(update_fields=['email_verified'])
        return True
    return user.profile.email_verified
```

so the registration is confirmed without the victim ever seeing a
verification email.

**Exploitation**

Logged-in attacker (Alice) submits the registration form for an event
with:

- `email = victim@example.com`
- `first_name = "🏆 Ride Leader"`
- `last_name  = "OBC Staff"`
- `phone      = +1 555 555 5555`

After submission:

- The victim's `User.first_name` / `last_name` / `UserProfile.phone` are
  silently rewritten to the attacker-chosen values. These names then
  appear on rider rosters, ride-leader emails, emergency-contact sheets,
  the admin UI, and Sentry PII.
- The victim is enrolled in the event in the `CONFIRMED` state — no
  verification email ever sent to them. They will only find out when
  the confirmation email arrives. Capacity is consumed.
- Worse: the victim is also marked `email_verified = True`, so *future*
  attacker registrations under that email will also skip verification.
  Once the flag is set, the attack works repeatedly without re-clicking
  any link.
- If the victim happened to have a usable password (e.g. they are an
  admin who logs in via `/admin/`), it has now been replaced with an
  unusable hash, locking them out of admin.

The same flaw also enables an unauthenticated attacker to (a) discover
whether an email belongs to a registered user by observing the
`DUPLICATE` redirect difference, and (b) overwrite that user's profile
data on every submission — they just can't skip verification.

**Remediation**

- When the request is authenticated, ignore the form's user-identity
  fields and use `request.user` directly. Only allow `email`,
  `first_name`, `last_name`, `phone` overrides on the *unauthenticated*
  path (where the verification email gates the change).
- Do not have `_should_skip_verification` trust
  `request_detail.authenticated` in isolation. The correct guard is
  "registration is for the same `User` as `request.user`" — i.e.
  `request.user.is_authenticated and request.user == user`.
- Do not mutate `email_verified` as a side effect of registration. Set
  it only when the verification token is actually consumed (which
  `verify_registration` already does). The current behaviour permanently
  trusts an unverified email after one drive-by authenticated POST.
- Do not call `set_unusable_password()` on existing users in
  `find_by_email_or_create`. That is a behaviour for newly-created
  accounts, not "anyone who happens to have this email."
- Do not silently rewrite an existing user's `first_name` /
  `last_name` / `phone` from a public form. Either ignore those fields
  when a user already exists, or require email verification before
  applying them.

---

## 3. (HIGH) `ALLOWED_HOSTS = ["*"]` in production

**Where**

- `ridehub/settings.py:22`

**Issue**

```python
if IS_HEROKU_APP:
    ALLOWED_HOSTS = ["*"]
```

Django explicitly documents that this is unsafe. It enables host
header injection (finding #1), cache poisoning of any CDN/proxy keyed
by host, password-reset poisoning if the Django auth reset is ever
used, and several other attacks that assume host validation is a
backstop.

Heroku does NOT enforce a host header for you — apps are accessible
on `*.herokuapp.com` and on whatever custom domain is configured. The
correct production list is the real public domain(s) only.

**Remediation**

```python
ALLOWED_HOSTS = [
    "obcrides.ca",
    "www.obcrides.ca",
    # plus the Heroku app domain if you actually use it
]
```

Combine with `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`
on Heroku so `request.is_secure()` returns true through the Heroku
router.

---

## 4. (MEDIUM-HIGH) `SESAME_ONE_TIME` env-var check effectively defaults to off

**Where**

- `ridehub/settings.py:84` — `SESAME_ONE_TIME = os.environ.get('SESAME_ONE_TIME') is not None`

**Issue**

`os.environ.get('SESAME_ONE_TIME') is not None` is True if and only if
the env var has been set to *any* value, *including the literal string
`'False'`*. So setting `SESAME_ONE_TIME=False` enables one-time tokens.
This is the opposite of every other operator's mental model and means
that in any deployment where this env var was never explicitly added,
sesame tokens are reusable.

Combined with finding #1, captured tokens can be replayed multiple
times within the 5-minute window. Combined with email forwarding,
referer leaks (clicking the login link goes to an authenticated page
which may emit a Referer to third-party scripts/images), or browser
history shared across devices, this is a real account-takeover risk
even without host-header injection.

**Remediation**

Default to one-time:

```python
SESAME_ONE_TIME = os.environ.get('SESAME_ONE_TIME', 'true').lower() in (
    'true', '1', 'yes', 'on'
)
```

Or just hard-code `SESAME_ONE_TIME = True`.

---

## 5. (MEDIUM) Expired-token verification path can be abused as an email bomber

**Where**

- `backoffice/services/registration_service.py:129-149`

**Issue**

```python
try:
    registration_id = signer.unsign(token, max_age=VERIFICATION_TOKEN_MAX_AGE)
except SignatureExpired:
    try:
        registration_id = signer.unsign(token)  # no max_age
    except BadSignature:
        return None, 'invalid'

    try:
        registration = Registration.objects.select_related(...).get(
            id=int(registration_id),
            state=Registration.STATE_UNVERIFIED,
        )
    except Registration.DoesNotExist:
        return None, 'not_found'

    self._send_verification_email(registration)  # ← sends mail
    return None, 'expired'
```

Anyone who has ever observed one valid (but now-expired) verification
token — for instance by glancing at an unverified user's inbox, an
email gateway log, or a forwarded message — can re-submit it
repeatedly to `/registrations/verify` and force the system to send a
fresh verification email to the victim each time. There is no rate
limit on this path.

**Remediation**

Don't re-send mail on the `expired` branch automatically. Instead,
render a "this link expired — request a new one" page that requires
the user to opt into a resend, ideally rate-limited per
registration / per email / per IP. Or, only attempt a resend when the
original signature is younger than some grace window (e.g. 7 days)
and only at most once per N minutes per registration.

---

## 6. (MEDIUM) `X-Forwarded-For` blindly trusted for audit IP

**Where**

- `backoffice/services/request_service.py:19-23`

```python
def _get_client_ip(self, request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
```

**Issue**

`X-Forwarded-For` is a client-controlled header. Any HTTP client can
send any value. The function takes the *first* element of the list,
which on a chain-of-proxies model is the value the original
*untrusted* client sent — exactly the opposite of what you want.

This value is then persisted to `Registration.ip_address` (per
migration 0051) and used for audit / abuse investigation.

**Exploitation**

An attacker registering for events can set
`X-Forwarded-For: 127.0.0.1` (or any IP they like, including a
colleague's or a competitor's) to frame someone else for spammy /
duplicate registrations.

**Remediation**

Heroku terminates SSL at the router and appends one IP to
`X-Forwarded-For`. The correct value is the *last* (rightmost) IP in
the list — and only if you trust the proxy chain to be exactly one
hop deep. Better: use a vetted helper such as
`django-ipware` configured for the Heroku proxy depth, or read the
first IP only after verifying `REMOTE_ADDR` is a known proxy IP.

Also set `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO',
'https')` so SSL detection is consistent.

---

## 7. (MEDIUM) JSON embedded in `<script>` via `|safe` allows HTML break-out

**Where**

- `web/views/reviews.py:69-81`
- `web/templates/web/reviews/2025.html:239-248`

**Issue**

The view does `json.dumps(...)` and the template renders the result
with `|safe` inside a `<script>` block:

```html
const monthlyLabels = {{ monthly_labels|safe }};
...
const locationsData = {{ locations_data|safe }};
```

Python's `json.dumps` does *not* escape `</` or `<!--`. If any of the
strings being dumped — program names, event locations, route names —
contains `</script>`, the dump will literally write `</script>` into
the HTML stream and close the `<script>` tag. The remaining JSON
content is then parsed as HTML, allowing arbitrary script injection.

Today, all of those strings come from admin-controlled models
(`Event.location`, `Program.name`, `Route.name`), so this requires
staff cooperation — but staff can be phished too, and the JSON-via-
safe pattern will rot the moment any of those fields becomes user-
supplied.

**Remediation**

Use Django's built-in `{{ value|json_script:"id" }}` template tag,
which emits a `<script type="application/json" id="id">...</script>`
with the proper escapes, then read it back in JS via
`JSON.parse(document.getElementById("id").textContent)`. As a
quick fix, post-process the JSON in the view:

```python
encoded = json.dumps(payload).replace('</', '<\\/').replace('<!--', '<\\!--')
```

---

## 8. (MEDIUM) No rate limiting on login or registration endpoints

**Where**

- `web/views/login.py` (`LoginFormView`)
- `web/views/registrations.py` (`registration_create`, `registration_verify`)

**Issue**

`POST /login/` accepts any email and triggers an email send (and a
sesame-token generation) every time. There is no throttle, captcha,
rate limit, or abuse mitigation. Combined with finding #1 (host
header injection), this turns into an outbound email bomb that can
also be used to spam any registered member with login emails — making
real phishing emails much less suspicious. Same is true of `POST
/events/<id>/registration` (sends confirmation/verification emails
for arbitrary email addresses) and `GET /registrations/verify`
(finding #5).

**Remediation**

Add rate limiting on these endpoints — per IP and per target email.
`django-ratelimit` is the usual choice; the existing celery
infrastructure could also drive an async throttle.

---

## 9. (MEDIUM) `CustomLoginView.dispatch` swallows all exceptions

**Where**

- `web/views/login.py:69-79`

**Issue**

```python
class CustomLoginView(SesameLoginView):
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            logger.info(f"Login failed with sesame token: {e}")
            return render(request, "web/login/login_expired.html")
```

This conflates "invalid token", "expired token", "tampered token",
"database down", "session backend down", "import error", etc. all
into the same friendly screen, and logs at `INFO`. Real attacks
(e.g. brute-forcing sesame tokens, replay attempts) are invisible.
Worse, if Sentry is configured to capture exceptions but not info
logs, they will not show up at all.

**Remediation**

Catch only the specific exceptions Sesame raises for bad/expired
tokens. Let any other exception propagate so it reaches Sentry.
Log brute-force attempts at WARNING or ERROR.

---

## 10. (LOW-MEDIUM) Missing security headers and cookie flags

**Where**

- `ridehub/settings.py` — production block

**Issue**

The production settings set `SECURE_SSL_REDIRECT = True` but do not
configure any of:

- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SESSION_COOKIE_HTTPONLY = True` (default in modern Django; worth being explicit)
- `SECURE_HSTS_SECONDS` / `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD`
- `SECURE_REFERRER_POLICY` (e.g. `'same-origin'`)
- `SECURE_CONTENT_TYPE_NOSNIFF` (default True; be explicit)
- `X_FRAME_OPTIONS` (default `'DENY'` would be safer than the implicit
  `'SAMEORIGIN'`)
- `SECURE_PROXY_SSL_HEADER` (needed on Heroku to make
  `request.is_secure()` correct)
- `CSRF_TRUSTED_ORIGINS` (Django ≥4 requires this for cross-origin
  CSRF over HTTPS for any subdomains)

Without `SESSION_COOKIE_SECURE`, the session cookie can leak the first
time SSL redirect fails or in any environment where SSL termination
takes a slow path; without HSTS the browser will downgrade attempts
for first-time visitors. Without `SECURE_REFERRER_POLICY`, clicking a
login link emits a Referer that may leak the sesame token to third
parties embedded in the destination page.

**Remediation**

```python
if IS_HEROKU_APP:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_TRUSTED_ORIGINS = ['https://obcrides.ca', 'https://www.obcrides.ca']
```

`SECURE_REFERRER_POLICY = 'same-origin'` (or `'strict-origin'`) is
particularly important for the magic-link flow: without it, the
landing page may leak the sesame token to any third-party resource
loaded on `/profile` (CDN images, fonts, analytics, Sentry's own JS).

---

## 11. (LOW-MEDIUM) `Azure AD tenant ID` defaults to empty string

**Where**

- `ridehub/settings.py:201-210` — `SOCIALACCOUNT_PROVIDERS`

**Issue**

```python
SOCIALACCOUNT_PROVIDERS = {
    'microsoft': {
        'TENANT': os.environ.get('AZURE_AD_TENANT_ID', ''),
        'VERIFIED_EMAIL': True,
        'APP': {
            'client_id': os.environ.get('AZURE_AD_CLIENT_ID', ''),
            'secret': os.environ.get('AZURE_AD_CLIENT_SECRET', ''),
        },
    }
}
```

If `AZURE_AD_TENANT_ID` is unset in production (or accidentally
cleared on a config rotation), `TENANT` is `''`. Depending on the
exact allauth version, this can fall back to the `common` endpoint,
which accepts logins from *any* Microsoft tenant including personal
accounts. Combined with:

- `SOCIALACCOUNT_EMAIL_AUTHENTICATION = True`
- `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True`
- `SOCIALACCOUNT_LOGIN_ON_GET = True`
- `VERIFIED_EMAIL: True` (allauth will *trust* the email Microsoft
  returns)
- Auto-staff-promotion in `RideHubSocialAccountAdapter._configure_obc_user`
  for any email ending in `@ottawabicycleclub.ca`

a misconfigured tenant could let anyone who controls (or convinces
Microsoft to issue) an `@ottawabicycleclub.ca` address in another
tenant become staff and take over the matching local account by
auto-connect.

This is a defence-in-depth concern rather than an active exploit — it
depends entirely on the tenant ID being configured. But because the
consequence is staff escalation, the default should fail closed.

**Remediation**

Fail loudly if the tenant ID is not set in production:

```python
if IS_HEROKU_APP:
    assert os.environ.get('AZURE_AD_TENANT_ID'), \
        'AZURE_AD_TENANT_ID must be set in production'
```

Also consider tightening `_configure_obc_user` to additionally check
that the social account provider is Microsoft and the tenant matches
the configured tenant — a belt-and-braces guard against an
auto-connect on an attacker-controlled email.

---

## 12. (LOW) `find_by_email_or_create` calls `set_unusable_password()` on existing users

**Where**

- `backoffice/services/user_service.py:36-37`

```python
case Some(user):
    if not user.is_staff:
        user.set_unusable_password()
```

**Issue**

Whenever an existing non-staff user is touched by the registration
flow, their password is wiped. This is intended (passwordless model),
but it makes the registration path a denial-of-service vector against
any non-staff user who *does* have a password (e.g. legacy accounts,
imported accounts, accounts created by an admin via
`createsuperuser` that were later demoted from staff).

Combined with finding #2, it gives an attacker a one-shot password
reset on the victim's account.

**Remediation**

Only set the unusable password during initial *creation* in the `_:`
branch. Don't touch the password of existing accounts from the
registration code path.

---

## 13. (LOW) `web/views/rides.py` builds HTML with f-strings

**Where**

- `web/views/rides.py:7-30`

**Issue**

```python
html = f'<select name="speed_range_preference" id="id_speed_range_preference" class="form-select">'
...
for speed_range in speed_ranges:
    is_selected = 'selected' if str(speed_range.id) == selected else ''
    html += f'<option value="{speed_range.id}" {is_selected}>{speed_range}</option>'
```

This is not an active XSS today because `speed_range.id` is an int
and `SpeedRange.__str__` returns `f"{lower_limit}-{upper_limit} km/h"`
(also numeric). But:

- The pattern bypasses Django's auto-escape entirely.
- The `selected` query parameter is taken from the user and *compared*
  to a string — there is no rejection of weird values; it just won't
  match. A future change that interpolates `selected` (or any new
  admin-editable field on `SpeedRange`) would silently become XSS.

**Remediation**

Use `django.utils.html.format_html` (which escapes all
parameters), or render this from a template. The whole function is
short enough that a one-line `format_html_join` call is cleaner.

---

## 14. (INFO) `lower_email` type signature uses `str|None` syntax inconsistently

**Where**

- `backoffice/utils.py:17`

Not a security issue, just brittle: `lower_email(email: str|None) -> str|None`
returns `None` for empty strings, but callers in
`web/views/login.py` call `lower_email(form.cleaned_data['email'])`
and immediately pass the result on without checking for `None`. Email
fields are validated as required, so this never fires in practice,
but it would crash if it did. Mentioned only because removing the
`None` handling from `lower_email` would make the contract clearer.

---

## 15. (INFO) `event_emergency_contacts` permission model

**Where**

- `web/views/events.py:308-329`

Worth noting that the real permission check is `is_ride_leader OR
is_staff` (line 322-323), which is correct. The
`HX-Request` header check on line 325 is a UX guard, not a security
control — `HX-Request` can be set by any HTTP client. The current
code does this correctly (the perm check runs first), but if anyone
ever rearranges the guards, do not let the `HX-Request` check come
first.

---

## Suggested fix order

If implemented in this order, each step measurably reduces blast radius:

1. **#3** — pin `ALLOWED_HOSTS`. One-line change, neutralises #1
   immediately.
2. **#4** — fix the `SESAME_ONE_TIME` default. One-line change,
   reduces token-replay window to zero.
3. **#1** — switch login link construction to `settings.WEB_HOST`.
   Defence in depth.
4. **#2** — fix the registration flow's identity handling. Largest
   change, but the highest-impact fix.
5. **#10** — add the missing security headers.
6. **#6**, **#5**, **#8** — input-trust / abuse mitigations.
7. **#7**, **#13** — XSS pattern hardening.
8. **#9**, **#11**, **#12** — defence in depth on auth paths.

---

## Out of scope / not reviewed

- The Django admin templates and built-in admin views beyond
  `templates/admin/login.html`.
- Third-party dependency CVEs (run `uv pip audit` or `safety` for
  that).
- Email template rendering — the only `|safe` data flowing into
  emails is the prose-editor description, which is server-sanitised.
- The Celery / Redis transport configuration (not visible in code).
- The Heroku environment / config-var contents.
