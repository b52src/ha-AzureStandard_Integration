"""Config flow for the Azure Standard integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_DROP_ID,
    CONF_EMAIL,
    CONF_MODE,
    CONF_PERSON_ID,
    CONF_SESSION_COOKIE,
    DOMAIN,
    MODE_ACCOUNT,
    MODE_MANUAL,
)


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODE, default=MODE_MANUAL): vol.In(
            [MODE_MANUAL, MODE_ACCOUNT]
        ),
    }
)

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DROP_ID): vol.Coerce(int),
        vol.Optional("name", default="Azure Standard"): str,
    }
)

STEP_ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required("password"): str,
    }
)


async def _validate_drop_id(
    hass: HomeAssistant,
    drop_id: int,
    client: "AzureStandardApiClient | None" = None,
) -> bool:
    """Return True if *drop_id* resolves to a valid drop via the public API.

    Uses the paginated GET /drops list since GET /drops/{id} returns 404.
    """
    from .api import AzureStandardApiClient

    if client is None:
        session = async_create_clientsession(hass)
        client = AzureStandardApiClient(session)
    try:
        drop = await client.get_drop_from_list(drop_id)
        return drop is not None
    except (aiohttp.ClientError, KeyError, ValueError):
        return False


class AzureStandardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial integration setup.

    Two paths are available:
    - **Manual**: user supplies a Drop ID directly (no credentials needed).
    - **Account**: user logs in; drop is detected from the account profile.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._mode: str | None = None
        # Preserved across account-path steps
        self._email: str = ""
        self._session_cookie: str = ""
        self._person_id: int | None = None
        self._detected_drop_id: int | None = None
        self._detected_drop_name: str = ""
        # Dedicated aiohttp session for the config flow (carries the cookie jar)
        self._http_session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Mode selection
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show mode-selection form (Manual vs Account login)."""
        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            if self._mode == MODE_MANUAL:
                return await self.async_step_manual()
            return await self.async_step_account()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
        )

    # ------------------------------------------------------------------
    # Manual path
    # ------------------------------------------------------------------

    async def async_step_manual(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Collect the Drop ID for manual (no-auth) mode."""
        errors: dict[str, str] = {}

        if user_input is not None:
            drop_id: int = user_input[CONF_DROP_ID]
            friendly_name: str = user_input.get("name", "Azure Standard")

            if not await _validate_drop_id(self.hass, drop_id):
                errors[CONF_DROP_ID] = "invalid_drop_id"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_manual_{drop_id}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=friendly_name,
                    data={
                        CONF_MODE: MODE_MANUAL,
                        CONF_DROP_ID: drop_id,
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Account path
    # ------------------------------------------------------------------

    async def async_step_account(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Collect email + password, authenticate, and detect the user's drop."""
        from .api import AzureStandardApiClient

        errors: dict[str, str] = {}

        if user_input is not None:
            # Use a dedicated session so the cookie jar is isolated to this flow
            if self._http_session is None:
                self._http_session = async_create_clientsession(self.hass)

            client = AzureStandardApiClient(self._http_session)

            try:
                success = await client.login(
                    user_input[CONF_EMAIL], user_input["password"]
                )
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="account",
                    data_schema=STEP_ACCOUNT_SCHEMA,
                    errors=errors,
                )

            if not success:
                errors["base"] = "invalid_auth"
            else:
                self._email = user_input[CONF_EMAIL]

                # Extract person ID and drop from session
                person_id, drop_id, drop_name = await _detect_drop_from_session(client)
                self._person_id = person_id
                self._detected_drop_id = drop_id
                self._detected_drop_name = drop_name

                # Snapshot the session cookie for storage in entry.data
                self._session_cookie = client.extract_cookie()

                return await self.async_step_drop_confirm()

        return self.async_show_form(
            step_id="account",
            data_schema=STEP_ACCOUNT_SCHEMA,
            errors=errors,
        )

    async def async_step_drop_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show the auto-detected drop; allow the user to override the drop ID."""
        errors: dict[str, str] = {}

        description_placeholders = {
            "drop_name": self._detected_drop_name or "unknown",
            "drop_id": str(self._detected_drop_id or ""),
        }

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DROP_ID,
                    description={"suggested_value": self._detected_drop_id},
                ): vol.Coerce(int),
            }
        )

        if user_input is not None:
            drop_id: int | None = user_input.get(CONF_DROP_ID) or self._detected_drop_id

            if not drop_id:
                errors[CONF_DROP_ID] = "missing_drop_id"
            elif not await _validate_drop_id(self.hass, drop_id):
                errors[CONF_DROP_ID] = "invalid_drop_id"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_account_{self._email}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Azure Standard ({self._email})",
                    data={
                        CONF_MODE: MODE_ACCOUNT,
                        CONF_EMAIL: self._email,
                        CONF_DROP_ID: drop_id,
                        CONF_PERSON_ID: self._person_id,
                        CONF_SESSION_COOKIE: self._session_cookie,
                    },
                )

        return self.async_show_form(
            step_id="drop_confirm",
            data_schema=schema,
            description_placeholders=description_placeholders,
            errors=errors,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _detect_drop_from_session(
    client: "AzureStandardApiClient",
) -> tuple[int | None, int | None, str]:
    """Return ``(person_id, drop_id, drop_name)`` using confirmed API paths.

    Step 1: GET /session  → personId  (integer, NOT a nested dict)
    Step 2: GET /drop-memberships?filter-person={personId}  → drop ID
    Step 3: GET /drops list, find the drop by ID → drop name

    Returns ``(None, None, "")`` on any failure so the flow still proceeds to
    the manual-override step.
    """
    # Step 1 — get personId from session
    try:
        session_data = await client.get_session()
    except aiohttp.ClientError:
        return None, None, ""

    # Confirmed shape: {"personId": 1674720, "person": 1674720, ...}
    # "person" is an integer, NOT a nested dict
    raw_person = session_data.get("personId") or session_data.get("person")
    if not raw_person:
        return None, None, ""
    try:
        person_id = int(raw_person)
    except (TypeError, ValueError):
        return None, None, ""

    # Step 2 — get drop ID from drop-memberships
    drop_id: int | None = await client.get_drop_id_for_person(person_id)
    if not drop_id:
        return person_id, None, ""

    # Step 3 — look up the drop name from the public list
    drop_name = ""
    try:
        drop_data = await client.get_drop_from_list(drop_id)
        if drop_data:
            drop_name = str(drop_data.get("name") or drop_data.get("dropName") or "")
    except aiohttp.ClientError:
        pass

    return person_id, drop_id, drop_name
