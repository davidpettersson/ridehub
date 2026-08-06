# React Frontend Migration Plan

## Context

RideHub is a Django 5.2 monolith on Heroku. The frontend today is 47 server-rendered
Bootstrap 5.3.2 templates driven by ~30 views in `web/`, with interactivity supplied by
CDN-loaded HTMX and Alpine. There is no API layer, no Node toolchain, no media storage,
and no map beyond a static PNG card fetched from RideWithGPS.

Three things are pushing a rewrite:

1. **Two UIs for one job.** Ride administrators work in Django admin, members and ride
   leaders work in `web/`. Neither audience gets a coherent product, and admin screens
   are unusable on a phone.
2. **Imagery.** Profile photos and event header images are wanted, and the current
   layouts have nowhere to put them. There is no `ImageField` anywhere in the codebase.
3. **Ride leaders on the road.** ~60% of traffic is iPhone. Ride leaders need rider
   lists, emergency contacts and route maps on a phone, mid-ride, one-handed.

The outcome: one React application at the same origin, where what you see is a function
of your permission level — member, ride leader (self-selected per event), ride
administrator (vetted staff). Django keeps the domain: models, services, validation,
Celery, email.

### Decisions already made

| Area | Decision |
|---|---|
| Cutover | **Admin-first.** 5 admin screens (~20 staff) → member browsing → ride-leader tools → registration flow last |
| UI layer | **Tailwind + shadcn/ui.** OBC palette becomes theme tokens; components copied into the repo, not a dependency |
| Design | Same palette, type, pills, badges, program colours. Refreshed layouts for imagery and thumb-reach |
| Hosting | **Same origin.** Vite builds into Django static; Django serves the SPA shell |
| Auth | **Unchanged.** DRF `SessionAuthentication` + CSRF header. Magic links and Azure AD keep working as-is |
| API shape | **Screen-shaped endpoints** delegating to `backoffice/services/`. drf-spectacular → openapi-typescript |
| Media | django-storages[s3] + presigned direct-to-S3 upload + Celery webp derivatives |
| Maps | Import the track from RideWithGPS into `Route`; render with MapLibre GL |
| Ride leader | **No new role, no migration.** Derived from a confirmed `Registration` with `ride_leader_preference = YES` |
| Django admin | The 5 rebuilt ModelAdmins become superuser-only break-glass. Everything else stays |
| Tests | Model/service tests untouched. View tests → API contract tests. Add vitest + a few Playwright flows |

---

## Step 0 — Branch and plan file

```
git switch -c 20260805-react-frontend-migration
```

This document lives at `PLAN.md` at the repo root on that branch.

---

## Phase 0 — Foundations

**Goal:** a React app builds, deploys, and serves at one URL prefix, with zero change to
any existing page.

### Frontend project

New `frontend/` directory at the repo root. Vite + React + TypeScript.

```
frontend/
  vite.config.ts
  package.json
  src/
    main.tsx            router + QueryClient
    routes/             one file per screen
    components/ui/      shadcn components, owned by us
    components/         OBC domain: EventCard, MetaPill, ForecastBadge, ProgramDot
    api/
      client.ts         fetch wrapper: credentials, X-CSRFToken, error normalisation
      types.ts          GENERATED from openapi.json — never hand-edited
    styles/theme.css    OBC tokens
```

Vite config:

```ts
base: '/static/app/',
build: { outDir: '../web/static/web/app', emptyOutDir: true },
server: { proxy: { '/api': 'http://localhost:8000' } }
```

Building into `web/static/web/app/` means `collectstatic` and whitenoise pick the bundle
up with no new storage backend and no manifest plumbing — the built `index.html` already
references its own hashed assets.

### Serving the shell

Add `web/static/web/app` to `TEMPLATES[0]['DIRS']` in `ridehub/settings.py` so the built
`index.html` is renderable as a template. Then a single view:

```python
def spa(request):
    return render(request, 'index.html')
```

Mount it in `ridehub/urls.py` under **one prefix only** for now:

```python
re_path(r'^manage/', spa),
```

`web/urls.py` stays untouched. No catch-all until Phase 6 — this is what keeps the
strangler safe.

### Design tokens

Port every colour from `web/static/web/styling.css` into `frontend/src/styles/theme.css`
as Tailwind v4 `@theme` tokens. The file currently mixes CSS custom properties with
hard-coded hex values scattered through rules; tokenise **all** of them:

| Token | Value | Used for |
|---|---|---|
| `--color-obc-blue` | `rgb(0,85,150)` | navbar, info accents |
| `--color-primary` | `#2563eb` | buttons, links, focus |
| `--color-primary-hover` | `#1d4ed8` | button hover |
| `--color-warning` | `#d97706` | warning announcements |
| `--color-danger` / `-hover` | `#dc2626` / `#b91c1c` | destructive actions |
| `--color-border` / `-hover` | `#b9c0c7` / `#6c757d` | pills, inputs |
| `--color-surface` / `-hover` | `#f9fafb` / `#f8f9fa` | body, hover states |
| `--color-body-text` | `#4b5563` | body copy |
| `--color-aqhi-{low,moderate,high,very-high}` | `#0891b2` … `#7f1d1d` | air-quality badges |
| `--color-ride-count-{1,2,3}` | `#2563eb`, `#6b93ec`, `#aac3f4` | ride-count badges |
| `--color-ride-leader` | `#0d9488` | ride-leader badge |
| `--color-success` | `#198754` | registered indicator |

Typography stays Inter (300/400/500/700). Program colour stays a per-instance CSS
variable (`--program-color`) applied inline, exactly as `.event-card::before` does today.

### Deployment

Add the Node buildpack **before** the Python one so `npm run build` produces the bundle
before `collectstatic` runs:

```
heroku buildpacks:add --index 1 heroku/nodejs
```

Root `package.json`:

```json
{ "scripts": { "heroku-postbuild": "npm --prefix frontend ci && npm --prefix frontend run build" } }
```

`Procfile` is unchanged.

### CI

Extend `.github/workflows/ci.yml` with a Node step before the Django step:
`npm ci`, `tsc --noEmit`, `vitest run`, `npm run build`, then `uv run python manage.py test`.
The Django suite must stay green throughout — building the bundle in CI is what keeps the
one test that asserts the SPA shell renders from failing.

**Verify:** `/manage/` returns the React shell; every existing page is byte-identical;
full suite green.

---

## Phase 0b — DRF foundations

New `api/` Django app. Prefix `/api/v1/`.

**Auth.** `SessionAuthentication` only — no tokens, no CORS, nothing added to the auth
flows described in `docs/users-authentication.md`. The SPA reads the `csrftoken` cookie
and sends `X-CSRFToken` on unsafe methods. One bootstrap endpoint:

```
GET /api/v1/session   @ensure_csrf_cookie
  → { authenticated, user: {id, first_name, last_name, email, avatar_url},
      permissions: { staff: bool, superuser: bool } }
```

This both sets the CSRF cookie and tells the SPA which nav to render.

**Permission classes** in `api/permissions.py`:

- `IsStaff` — ride administrator. Mirrors `_require_staff` at
  `web/views/registration_manage.py:18`.
- `IsEventRideLeaderOrStaff` — reuses the exact query already written at
  `web/views/events.py:31` (`_is_confirmed_ride_leader`). **Move that function into
  `backoffice/services/registration_service.py` and have both the old view and the new
  permission class call it**, so there is one definition during the transition.
- `IsSelf` — profile and own-registration endpoints.

**Response shape.** DRF defaults. No custom envelope — drf-spectacular describes the
defaults accurately and openapi-typescript generates from them.

**Pagination.** `PageNumberPagination` on admin list endpoints only. Member endpoints
return complete result sets, matching today's behaviour (no view in `web/` paginates).

**Type generation.** `drf-spectacular` writes `openapi.json`; an npm script runs
`openapi-typescript` into `frontend/src/api/types.ts`. A CI check fails if the committed
types drift from the schema.

**Data fetching.** TanStack Query over the `client.ts` fetch wrapper. No Redux, no
generated client — the generated *types* plus plain fetch are enough.

**Security rule that carries into every phase:** name masking and contact visibility are
decided **server-side, before serialization**. `RegistrationService.mask_hidden_names`
(called at `web/views/events.py:139` and `:312`) and the `exclude_columns` logic at
`web/views/events.py:319-327` must become serializer-level field omission. Hidden names
and emergency contacts must never reach the client, not even hidden by CSS.

---

## Phase 1 — The five admin screens (~20 staff, desktop-first)

React at `/manage/*`. Endpoints under `/api/v1/manage/`, all `IsStaff`.

| Screen | Endpoints | Notes |
|---|---|---|
| Announcements | `GET/POST /announcements`, `GET/PUT/DELETE /announcements/{id}` | rich text; type + audience selects |
| Programs | `GET/POST /programs`, `GET/PUT/DELETE /programs/{id}` | colour picker, emoji, article, archived |
| Speed ranges | `GET/POST /speed-ranges`, `GET/PUT/DELETE /speed-ranges/{id}` | trivial; two integers |
| Routes | `GET /routes`, `GET/PUT /routes/{id}`, `POST /routes/{id}/import` | list filters archived/deleted; import calls `backoffice/services/route_service.py` |
| Events | `GET /events`, `GET/POST/PUT /events/{id}` | the hard one, below |

### Event editing

Reproduce `EventAdmin` (`backoffice/admin.py:46-125`) as three sections matching its
existing fieldsets: general, registration options, registration form settings. The
read-only cancellation / reschedule / archival blocks appear conditionally, same as
`get_fieldsets`.

**Nested rides.** Today these are an `adminsortable2` `SortableStackedInline`
(`backoffice/admin.py:31`). In the API, `GET /manage/events/{id}` returns rides as an
ordered array; `PUT` accepts the full array and derives `Ride.ordering` from array index.
Drag-reorder in React via `dnd-kit`. Route selection is a searchable combobox backed by
`GET /manage/routes?q=`.

**State transitions.** Do not expose `state` as a writable field. The FSM guards in
`backoffice/models.py:399-421` (notably `has_no_confirmed_registrations`) must not be
bypassable:

```
POST /manage/events/{id}/actions/{announce|draft|live|cancel|reschedule|archive|duplicate}
```

each delegating to `backoffice/actions.py`. `cancel` and `reschedule` take a reason;
`reschedule` takes new times. A `FSMTransitionNotAllowed` maps to HTTP 409 with the
reason. `GET /manage/events/{id}` returns the list of currently-allowed transitions so
the UI can disable buttons rather than discover failures.

**Rich text.** `Event.description`, `Ride.description` and `Announcement.text` are
`ProseEditorField(sanitize=True)`. Use Tiptap in React — the same engine
django-prose-editor wraps — configured with the identical extension set from
`PROSE_EDITOR_CONFIG` (`backoffice/models.py:12-24`). The editor posts an HTML string;
**sanitization stays server-side** via the existing `sanitize=True` path. Never trust the
client's HTML.

**Audit.** `AuditedAdminMixin` (`backoffice/admin.py:13`) wraps saves in
`actor(request.user)`. The API must do the same — an `api/mixins.py` performing writes
inside `with actor(request.user):`, or audit trails silently stop for anything edited
through React.

**Django admin.** Add to each of the five ModelAdmins:

```python
def has_view_permission(self, request, obj=None):
    return request.user.is_superuser
```

Keep them registered as break-glass.

**Verify:** a staff user creates a program, a route, an event with three drag-ordered
rides, announces it, cancels it with a reason — and the audit log shows every step.

---

## Phase 2 — Member browsing

| Screen | Endpoint | Source view |
|---|---|---|
| Upcoming list | `GET /api/v1/events?q=` | `web/views/events.py:249` |
| Calendar | `GET /api/v1/events/calendar?year=&month=&q=` | `web/views/events.py:433` |
| Event detail | `GET /api/v1/events/{id}` | `web/views/events.py:166` |
| Forecast history | `GET /api/v1/events/{id}/forecasts` | `web/views/events.py:228` |
| Announcements | `GET /api/v1/announcements/active` | `web/views/announcements.py` |
| Static pages | `GET /api/v1/pages/{slug}` | `web/views/pages.py` |

**Event detail is one request**, returning event + rides + routes + speed ranges + rider
groupings + the viewer's own registration + capacity + forecast. The grouping logic at
`web/views/events.py:48-148` moves into a service method, not a serializer.

**Reuse, do not reimplement.** `backoffice/services/forecast_summary.py:summarize`
already produces the badge fields (condition, temperature display, AQHI category,
warnings). Serialize its output; do not re-derive weather logic in TypeScript. Same for
`EventService.fetch_upcoming_events`, `fetch_events_for_month`, `fetch_forecasts` and
`RegistrationService.fetch_confirmed_event_ids`.

**Stays server-rendered permanently:** `events.ics` (django-ical), `robots.txt`, all
`web/templates/email/*` (and their tests in `web/tests/templates/test_email_templates.py`),
Django admin, allauth pages, `500.html`.

**Session state moves to the client.** `preferred_events_view`, `calendar_selected_year`
and `calendar_selected_month` (`web/views/events.py:152-163, 447-448`) become
localStorage. The `events_redirect` view survives only until Phase 6.

**Mobile.** The calendar is already a custom mobile widget (`.calendar-day-mobile`, dots,
tap-to-expand). Rebuild it faithfully — it is the most-used member screen on a phone.
Event cards gain a 16:9 header image slot that collapses cleanly when absent, which is
the state for every existing event.

---

## Phase 3 — Ride leader and staff registration management

The functionality most in need of a phone-first redesign.

| Screen | Endpoint | Permission |
|---|---|---|
| Rider list | `GET /api/v1/events/{id}/registrations` | public, field-filtered |
| Reveal contacts | `GET /api/v1/events/{id}/registrations?contacts=1` | `IsEventRideLeaderOrStaff`, audit-logged |
| Emails | `GET /api/v1/events/{id}/registrations/emails?type=leaders` | same, audit-logged |
| Manage list | `GET /api/v1/manage/events/{id}/registrations` | `IsStaff` |
| Staff add/edit | `POST/PUT /api/v1/manage/events/{id}/registrations[/{rid}]` | `IsStaff` |
| Staff withdraw | `POST /api/v1/manage/events/{id}/registrations/{rid}/withdraw` | `IsStaff` |

`django-tables2` and `django-filter` disappear from these screens. The filtering logic in
`web/filters.py` moves into API queryset filtering; the column-exclusion logic
(`web/views/events.py:319-327`) becomes conditional serializer fields.

**Phone numbers.** The API returns two fields per number: `phone_display` and `phone_uri`,
produced by the existing filters in `web/templatetags/phone_filters.py`. This preserves
the CLAUDE.md rule that a raw phone field never lands in an `href` — the normalisation
stays server-side rather than being re-implemented in TypeScript.

**Mobile ergonomics for on-the-road use:**
- Sticky bottom action bar (Reveal contacts · Emails · Print) within thumb reach
- Rows are ≥56px tap targets; tapping a rider opens a sheet with tap-to-call and
  tap-to-text emergency contact links
- Search and ride/speed filters in a bottom sheet, not a top bar
- Contact reveal is a deliberate two-step action, and stays audit-logged
  (`web/views/events.py:394`, `:411`, `:428`)

**Print stays server-rendered.** `registrations_print.html` is a print stylesheet
problem, used rarely, and works today. Leave it on Django; link out to it.

---

## Phase 4 — Registration flow and profile (highest risk, last)

| Flow | Endpoints |
|---|---|
| Register | `POST /api/v1/events/{id}/registration` → `RegistrationService` |
| Edit / withdraw own | `PUT`/`POST …/withdraw` on `/api/v1/registrations/{id}`, `IsSelf` |
| Membership number | `POST /api/v1/profile/membership-number` |
| Name visibility | `PUT /api/v1/profile/name-visibility` |
| Request magic link | `POST /api/v1/auth/login-link` |

**Email-borne links stay Django views.** A verification or magic link arriving from an
email client must establish a session server-side and then redirect into an SPA route
(`/events/{id}?verified=1`). Do not attempt to handle sesame tokens in JavaScript.
`web/views/login.py` and `registration_verify` keep working unchanged.

**De-risking.** `django-waffle` is already a dependency and already used in templates.
Put the React registration flow behind a flag; run both paths against the same service
layer; enable for staff, then a percentage, then everyone. The Django registration views
stay live until the flag has been at 100% for a full event cycle.

**Validation parity is the risk.** `Registration.clean` (`backoffice/models.py:931-975`)
enforces seven conditional rules (emergency contact required, ride-leader preference
required, speed range must belong to the ride, prospective-member and first-time-attendee
required when asked). The API must surface these as per-field errors, and the React form
must render them per field. Port `web/tests/test_forms.py` and
`web/tests/views/test_registration_views.py` case-for-case into API tests before writing
the React form.

---

## Phase 5 — Media and maps

### Images

```python
Event.header_image = ImageField(upload_to='events/', blank=True)
UserProfile.avatar = ImageField(upload_to='avatars/', blank=True)
```

- `django-storages[s3]` + `boto3`; `STORAGES['default']` → S3 when `AWS_STORAGE_BUCKET_NAME`
  is set, filesystem locally. Static storage stays whitenoise.
- `POST /api/v1/uploads/presign` → presigned PUT. Bytes never touch a dyno.
  Validate content type and size limits server-side when issuing the presign, and
  re-validate the object on confirmation.
- Celery task generates 400w/800w/1600w webp derivatives; the API returns a srcset.
- Both fields are optional and every layout must look intentional when empty — that is
  the state of 100% of existing rows.

### Routes and GPX

`Route` today holds only a RideWithGPS URL, `distance`, `elevation_gain`
(`backoffice/models.py:424-483`). The "map" is `<img src=".../card.png">`
(`web/templates/cotton/rwgps_map.html`). Add:

```python
Route.polyline          = TextField(blank=True)      # encoded polyline
Route.bounds            = JSONField(null=True)       # [[minLat,minLng],[maxLat,maxLng]]
Route.elevation_profile = JSONField(null=True)       # [[distance_m, elevation_m], …]
Route.track_imported_at = DateTimeField(null=True)
```

Extend the existing `backoffice/services/route_service.py` import — it already talks to
RideWithGPS — with a Celery task that fetches and stores the track. Simplify the
polyline server-side to a few hundred points; a full 40km GPX track is tens of thousands
of coordinates and will stutter on a phone.

### MapLibre component

- Vector tiles from MapTiler or Protomaps; key injected at build time.
- `cooperativeGestures: true` — one finger scrolls the page, two fingers pan the map.
  Non-negotiable on mobile; without it the map traps the scroll.
- Height 240px on mobile, 420px on desktop; fit to `bounds` on load; start/finish markers.
- Elevation profile as a small inline SVG below the map, hover/touch syncing a marker.
- Fall back to distance/elevation pills when `polyline` is empty.

---

## Phase 6 — Decommission

Per surface, in this order: (1) React screen live and verified, (2) old template and view
deleted, (3) old URL 301s to the SPA route, (4) template tests deleted, view tests
already converted.

Finally, replace the per-prefix SPA mounts with a catch-all below `web/urls.py`, and
delete `_base_bootstrap.html`, `styling.css`, the HTMX/Alpine CDN tags, and the
`django-tables2` / `django-filter` / `django-cotton` dependencies.

Keep permanently: Django admin, allauth and sesame views, iCal feed, robots.txt, all
email templates and their tests.

---

## Effort

| Phase | Relative effort | Ships to |
|---|---|---|
| 0 + 0b foundations | Medium | nobody |
| 1 admin screens | Large | ~20 staff |
| 2 member browsing | Large | everyone |
| 3 ride leader tools | Medium | ride leaders + staff |
| 4 registration + profile | Large | everyone |
| 5 media + maps | Medium | everyone |
| 6 decommission | Small | — |

The dominant cost is not React. It is converting ~30 view tests plus their template tests
into API contract tests while keeping the suite green at every commit.

---

## Risks

1. **Data leakage through serializers.** Name masking and contact visibility are today
   enforced by template-level column exclusion. In an API, forgetting a conditional field
   ships hidden names and emergency phone numbers to every client. Every registration
   serializer needs an explicit test that asserts the field is *absent* for an
   unprivileged viewer.
2. **Registration validation drift.** Seven conditional rules in `Registration.clean`.
   Contract tests before UI.
3. **Ride-leader permission cost.** Derived-from-registrations means a subquery per
   request on every ride-leader endpoint. Acceptable at current scale; add an index on
   `Registration(event, user, state)` if it shows up in Sentry.
4. **FSM bypass.** `state` must never be a writable serializer field.
5. **Audit gap.** Writes through the API must run inside `actor(request.user)`.
6. **Build complexity on Heroku.** Two buildpacks, longer builds, larger slug. Node
   version must be pinned in `frontend/package.json` `engines`.
7. **Session-state assumptions.** Several views write to `request.session` for view
   preferences; these silently stop working when the SPA takes over the page.
8. **Tile provider cost.** MapLibre needs a tile source with a free tier and a billing
   ceiling.

## Open questions

- Which tile provider, and who owns the key?
- Should the SPA live at `/` eventually, or stay under prefixes indefinitely?
- Do event header images need moderation, or is staff-only upload sufficient?

---

## Verification

- **Every phase:** `uv run python manage.py test` — zero failures, zero errors. This is
  non-negotiable per CLAUDE.md and is the gate on every push.
- **Frontend:** `tsc --noEmit`, `vitest run`, `npm run build` in CI.
- **Contract drift:** CI regenerates `openapi.json` and fails if `frontend/src/api/types.ts`
  is stale.
- **End-to-end (Playwright, small and targeted):**
  1. Staff creates an event with two rides, announces it, cancels it with a reason
  2. Member registers for an event, receives confirmation, edits, withdraws
  3. Ride leader opens the rider list on an iPhone viewport, reveals contacts, taps to call
  4. Anonymous registration → verification email → link → signed in and confirmed
- **Manual, on a real iPhone, before each member-facing phase ships:** calendar, event
  detail with a route map, and the rider list. Simulators do not reproduce
  `cooperativeGestures` or thumb reach.
- **Security check before Phase 3 ships:** as an anonymous user and as a plain member,
  request every registration endpoint and assert no masked name, email, phone, or
  emergency contact appears in any response body.
