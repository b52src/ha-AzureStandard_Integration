"""Azure Standard — Home Assistant Integration."""
from __future__ import annotations

import logging
import pathlib

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AzureStandardApiClient
from .const import DOMAIN
from .coordinator import AzureStandardCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Panel registration constants
_PANEL_JS      = "azure-standard-panel.js"
_PANEL_ELEMENT = "azure-standard-panel"
_PANEL_TITLE   = "Azure Standard"
_PANEL_ICON    = "mdi:sprout"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the www/ directory so HA serves the panel JS file."""
    www_path = pathlib.Path(__file__).parent / "www"
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path="/azure_standard_panel",
            path=str(www_path),
            cache_headers=True,
        )
    ])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azure Standard from a config entry."""
    session = async_get_clientsession(hass)
    client = AzureStandardApiClient(session)

    coordinator = AzureStandardCoordinator(
        hass,
        entry=entry,
        client=client,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Register the sidebar panel (idempotent — skip if already registered by
    # a previous config entry for this domain).
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=_PANEL_ELEMENT,
            frontend_url_path=DOMAIN,
            module_url=f"/azure_standard_panel/{_PANEL_JS}",
            sidebar_title=_PANEL_TITLE,
            sidebar_icon=_PANEL_ICON,
            require_admin=False,
            config={},
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove the panel when the last config entry is unloaded.
    if not hass.data.get(DOMAIN):
        hass.components.frontend.async_remove_panel(DOMAIN)

    return unloaded


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
