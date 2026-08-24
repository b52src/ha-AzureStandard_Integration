"""Config flow for the Azure Standard integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DROP_ID,
    CONF_EMAIL,
    CONF_MODE,
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


async def _validate_drop_id(hass: HomeAssistant, drop_id: int) -> bool:
    """Return True if *drop_id* resolves to a valid drop via the public API."""
    from .api import AzureStandardApiClient

    session = async_get_clientsession(hass)
    client = AzureStandardApiClient(session)
    try:
        drop = await client.get_drop(drop_id)
        return bool(drop)
    except (aiohttp.ClientError, KeyError):
        return False


class AzureStandardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial integration setup.

    Two paths are available:
    - **Manual**: user supplies a Drop ID directly (no credentials needed).
    - **Account**: user logs in; drop is detected automatically.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._mode: str | None = None
        self._account_data: dict = {}

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
    # Account path  (credential collection — Phase 3 completes this)
    # ------------------------------------------------------------------

    async def async_step_account(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Collect email + password and validate the login."""
        from .api import AzureStandardApiClient

        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = AzureStandardApiClient(session)
            success = await client.login(
                user_input[CONF_EMAIL], user_input["password"]
            )

            if not success:
                errors["base"] = "invalid_auth"
            else:
                self._account_data = {
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_MODE: MODE_ACCOUNT,
                }
                try:
                    session_data = await client.get_session()
                    self._account_data["_session_data"] = session_data
                except aiohttp.ClientError:
                    pass

                return await self.async_step_drop_confirm()

        return self.async_show_form(
            step_id="account",
            data_schema=STEP_ACCOUNT_SCHEMA,
            errors=errors,
        )

    async def async_step_drop_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Show detected drop; allow the user to override the drop ID."""
        errors: dict[str, str] = {}

        # Detect drop from session data
        session_data = self._account_data.pop("_session_data", {})
        detected_drop_id: int | None = None
        detected_drop_name: str = ""
        try:
            # The session payload contains person → defaultDrop or similar
            person = session_data.get("person", {})
            detected_drop_id = person.get("dropId") or person.get("drop-id")
            detected_drop_name = str(person.get("dropName", ""))
        except (AttributeError, KeyError):
            pass

        description_placeholders = {
            "drop_name": detected_drop_name or "unknown",
            "drop_id": str(detected_drop_id or ""),
        }

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DROP_ID, default=detected_drop_id or vol.UNDEFINED
                ): vol.Coerce(int),
            }
        )

        if user_input is not None:
            drop_id = user_input.get(CONF_DROP_ID) or detected_drop_id
            if not drop_id:
                errors[CONF_DROP_ID] = "missing_drop_id"
            elif not await _validate_drop_id(self.hass, drop_id):
                errors[CONF_DROP_ID] = "invalid_drop_id"
            else:
                await self.async_set_unique_id(
                    f"{DOMAIN}_account_{self._account_data[CONF_EMAIL]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Azure Standard ({self._account_data[CONF_EMAIL]})",
                    data={
                        **self._account_data,
                        CONF_DROP_ID: drop_id,
                    },
                )

        return self.async_show_form(
            step_id="drop_confirm",
            data_schema=schema,
            description_placeholders=description_placeholders,
            errors=errors,
        )
