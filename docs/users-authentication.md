# User Authentication in RideHub

This document describes the authentication methods available in RideHub and when each is used.

## Authentication Methods

### 1. Passwordless Email Links (Primary)

**For**: All registered members

This is the primary authentication method for the thousands of club members who have registered for rides.

**How it works**:
1. User visits `/login/` and enters their email address
2. System generates a secure, time-limited token using django-sesame
3. An email is sent with a login link containing the token
4. User clicks the link and is automatically logged in

**Configuration** (in `settings.py`):
- `SESAME_MAX_AGE`: Token validity period (default: 5 minutes)
- `SESAME_ONE_TIME`: If set, tokens can only be used once

**Requirements**:
- User must have previously registered for at least one ride
- Email address must match an existing account

### 2. Microsoft Azure AD (Secondary)

**For**: Club volunteers with @ottawabicycleclub.ca accounts

Club board members and volunteers who have Microsoft 365 accounts can sign in directly without waiting for an email.

**Feature flag**: This feature is controlled by a Waffle switch named `microsoft_login`. To enable:
1. Go to Django Admin > Waffle > Switches
2. Add a switch named `microsoft_login`
3. Check the "Active" checkbox to enable

**How it works**:
1. User clicks "Sign in with Microsoft" on the login page
2. User is redirected to Microsoft's login page
3. After authentication, Microsoft returns the user's profile (email, name)
4. If a RideHub account exists with that email, it's automatically linked
5. User is logged in

**Auto-linking behavior**:
- If an @ottawabicycleclub.ca user already has a RideHub account (from ride registrations), their Microsoft identity is linked to the existing account
- All existing data (registrations, profile) is preserved
- Future logins via Microsoft are instant

**Configuration**:
- Requires Azure AD app registration (see `docs/azure-setup.md`)
- Environment variables: `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`, `AZURE_AD_TENANT_ID`
- Restricted to the Ottawa Bicycle Club tenant only

### 3. Django Admin (Superusers Only)

**For**: Site administrators

Traditional username/password authentication is available only through the Django admin interface at `/admin/`.

**How it works**:
- Superuser accounts are created via `python manage.py createsuperuser`
- These accounts use Django's built-in password authentication
- Only used for administrative access, not for the main application

## User Lifecycle

### Account Creation

Users are created in RideHub through:

1. **Event registration**: When someone registers for a ride, their account is created via `UserService.find_by_email_or_create()`
2. **Azure AD first login**: If a volunteer signs in via Microsoft and no account exists, one is created automatically

### UserProfile

Every user automatically gets a `UserProfile` created via a Django signal. The profile stores:
- Phone number
- Gender identity (optional)
- Legacy flag (for imported data)

### Email Normalization

All email addresses are lowercased for consistency. This ensures:
- `John.Doe@example.com` and `john.doe@example.com` are treated as the same account
- Azure AD logins correctly match existing accounts

## Security Considerations

- No passwords are stored for regular users (passwordless design)
- Email tokens are short-lived (5 minutes default) and optionally single-use
- Azure AD tenant restriction prevents unauthorized Microsoft accounts
- Admin accounts should use strong passwords and are separate from member accounts
