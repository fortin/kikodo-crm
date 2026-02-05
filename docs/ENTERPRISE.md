# Enterprise features

## SSO / SAML

To add SAML or OAuth-based SSO so enterprises can use IdP-backed login:

- **django-allauth**: Supports OAuth2 and OpenID Connect; add `allauth` to `INSTALLED_APPS` and configure providers (Google, Microsoft, etc.).
- **django-saml2** or **python3-saml**: For SAML 2.0; configure your IdP metadata and SP settings in Django.

After installing, set `LOGIN_URL` and optionally `LOGIN_REDIRECT_URL` in settings and wire the login view.

## Forecasting

The **Deals > Forecast** view shows pipeline value by stage and by owner (total and probability-weighted). Use it for commit/best-case views and rep performance.

## Webhooks

Configure outbound webhooks in **Admin > CRM > Webhooks**. Each webhook has a URL, optional secret (for HMAC-SHA256 `X-Webhook-Signature`), and event subscriptions (e.g. `contact.create`, `deal.update`). On each event the payload is POSTed as JSON with `event`, `model`, `object_id`, `old_values`, `new_values`, and `timestamp`.

## Rate limiting

The REST API uses `UserRateThrottle` (100 requests/hour per user by default). Adjust `DEFAULT_THROTTLE_RATES` in settings if needed.
