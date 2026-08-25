# Google sign-in setup

The application code is ready for Google sign-in. You only need to create a free OAuth client and add its two private values to `Backend/.env`.

## 1. Create the Google project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project named `Abhyaas` or select an existing project.
3. Open **Google Auth Platform**.
4. Complete the branding page with the application name and your support email.
5. Choose **External** audience while testing.
6. Add your own Google account under **Test users**.

Only the basic `openid`, `email`, and `profile` scopes are requested. Abhyaas does not request access to Drive, Gmail, Calendar, or other Google data.

## 2. Create the OAuth client

1. Open **Google Auth Platform → Clients**.
2. Select **Create client**.
3. Choose **Web application**.
4. Add this authorized JavaScript origin:

```text
http://localhost:3000
```

5. Add this authorized redirect URI exactly:

```text
http://localhost:8001/api/v1/auth/google/callback
```

The scheme, host, port, path, and trailing slash must match exactly.

## 3. Add the private credentials

Google displays a **Client ID** and **Client secret**. Open `Backend/.env` and fill in:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8001/api/v1/auth/google/callback
```

Never put the client secret in the frontend, send it in chat, or commit `.env` to Git.

## 4. Start the applications

Backend:

```powershell
cd C:\Users\kanja\OneDrive\Desktop\Abhyaas\Backend
.\scripts\start_backend.ps1
```

Frontend:

```powershell
cd C:\Users\kanja\OneDrive\Desktop\Abhyaas\Frontend\abhyaas
npm run dev
```

Open `http://localhost:3000/login` and select **Sign in with Google**.

## Security used by this flow

- Google authorization-code flow on the backend.
- PKCE code challenge.
- Cryptographically random `state` value for CSRF protection.
- OpenID Connect nonce validation.
- Google ID-token signature, issuer, audience, and expiry validation.
- Only verified Google email addresses are accepted.
- Google tokens are not stored by Abhyaas.
- Abhyaas creates its own rotating, hashed seven-day session after Google confirms identity.

Official reference: [Google OAuth 2.0 for web-server applications](https://developers.google.com/identity/protocols/oauth2/web-server).
