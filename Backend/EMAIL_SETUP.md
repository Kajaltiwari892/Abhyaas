# Production password-reset email

Abhyaas uses SMTP only for transactional account emails. Local development keeps using the
console provider, which prints links in the backend terminal.

## Free Gmail setup

1. Turn on 2-Step Verification for the sender Google account.
2. Open Google Account **Security > App passwords**.
3. Create an app password named `Abhyaas email` and copy the generated 16-character value.
4. Never place the app password in Git, screenshots, chat, or frontend environment variables.
5. Store it only as the backend's `SMTP_PASSWORD` environment variable.

Production backend variables:

```text
EMAIL_PROVIDER=smtp
EMAIL_FROM_ADDRESS=kanjal55567@gmail.com
EMAIL_FROM_NAME=Abhyaas
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=kanjal55567@gmail.com
SMTP_PASSWORD=<Google app password>
SMTP_USE_SSL=true
```

The password-reset endpoint waits for Gmail to accept the message before returning success.
Reset tokens are random, single-use, expire after 30 minutes, and only their hashes are stored.

To return to local console delivery, use `EMAIL_PROVIDER=console` only when
`APP_ENV=development`.
