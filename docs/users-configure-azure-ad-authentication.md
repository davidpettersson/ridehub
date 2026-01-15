# Azure AD Setup for RideHub

This guide explains how to configure Microsoft Entra ID (Azure AD) to allow Ottawa Bicycle Club volunteers to sign in to RideHub using their @ottawabicycleclub.ca Microsoft 365 accounts.

## Prerequisites

- Admin access to the Ottawa Bicycle Club Microsoft 365 tenant
- Access to the Azure Portal (portal.azure.com)

## Step 1: Register the Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** (formerly Azure Active Directory)
3. Select **App registrations** from the left menu
4. Click **New registration**

### Registration Details

- **Name**: `RideHub`
- **Supported account types**: Select **Accounts in this organizational directory only (Ottawa Bicycle Club only - Single tenant)**
- **Redirect URI**:
  - Platform: **Web**
  - URL: `https://obcrides.ca/accounts/microsoft/login/callback/`

5. Click **Register**

## Step 2: Note the Application IDs

After registration, you'll see the application overview page. Record these values:

| Value | Description |
|-------|-------------|
| **Application (client) ID** | A UUID like `12345678-1234-1234-1234-123456789abc` |
| **Directory (tenant) ID** | A UUID identifying the OBC tenant |

## Step 3: Create a Client Secret

1. In the app registration, select **Certificates & secrets** from the left menu
2. Under **Client secrets**, click **New client secret**
3. Enter a description: `RideHub Production`
4. Select an expiration period (recommended: 24 months)
5. Click **Add**

**IMPORTANT**: Copy the **Value** of the secret immediately. It will only be shown once and cannot be retrieved later.

| Value | Description |
|-------|-------------|
| **Client secret value** | The secret string (copy immediately!) |

## Step 4: Configure Redirect URIs (Optional)

If developers need to test locally, add an additional redirect URI:

1. Go to **Authentication** in the left menu
2. Under **Web** platform, click **Add URI**
3. Add: `http://localhost:8000/accounts/microsoft/login/callback/`
4. Click **Save**

## Step 5: Verify API Permissions

The default permissions should be sufficient. Verify:

1. Go to **API permissions** in the left menu
2. Ensure **Microsoft Graph > User.Read** is listed
3. If not present, click **Add a permission** > **Microsoft Graph** > **Delegated permissions** > **User.Read**

## Values to Provide to Developers

Send these three values securely to the development team:

```
AZURE_AD_CLIENT_ID=<Application (client) ID>
AZURE_AD_CLIENT_SECRET=<Client secret value>
AZURE_AD_TENANT_ID=<Directory (tenant) ID>
```

## Security Notes

- The client secret should be treated like a password
- Rotate the secret before it expires
- Only users with @ottawabicycleclub.ca accounts can sign in (tenant restriction)
- The secret will need to be rotated before the expiration date

## Troubleshooting

### "AADSTS50194" Error
This error occurs if the app is configured for multi-tenant but the tenant setting is wrong. Ensure:
- App registration is set to "Single tenant"
- The `AZURE_AD_TENANT_ID` environment variable contains the correct tenant ID

### "Invalid redirect URI" Error
Ensure the redirect URI in Azure matches exactly:
- Production: `https://obcrides.ca/accounts/microsoft/login/callback/`
- Local dev: `http://localhost:8000/accounts/microsoft/login/callback/`

Note the trailing slash is required.
