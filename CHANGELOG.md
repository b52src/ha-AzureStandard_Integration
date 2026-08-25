# Changelog

## [0.0.6] - 2025-07-14

### Fixed
- **`hass.components` removed in HA 2025.1** — replaced deprecated `hass.components.persistent_notification.async_create(...)` with the modern `persistent_notification.async_create(hass, ...)` import. This was causing "Failed setup, will retry" on every integration load.
- **Auth failures silently swallowed** — `_authenticated_get` now correctly raises `ConfigEntryAuthFailed` when the post-reauth retry also receives a 401/403, instead of raising a raw `aiohttp.ClientResponseError` that was caught and logged as a transient network warning ("Failed to refresh orders; keeping previous data.").
- **`_authenticated_get` never retried** — the docstring said "retry once after re-auth" but the code re-raised the original error immediately after calling `_reauth()`. The request is now retried after a successful re-login.
- **Network errors triggered unnecessary reauth** — a `ClientError` during `validate_session()` (e.g. a momentary network blip) incorrectly set `valid = False`, which then called `_reauth()`. Network errors are now treated as transient and the session check is skipped until the next interval.

## [0.0.5] - 2025-07-13

### Added
- Silent re-authentication using stored password when session cookie expires.
- `CONF_PASSWORD` stored in config entry data on initial setup and reauth flow.
- `_reauth()` coordinator helper: re-logs in and persists the fresh session cookie.
- Reauth config flow (`async_step_reauth` / `async_step_reauth_confirm`) prompts the user via the HA repair UI when no password is stored.
