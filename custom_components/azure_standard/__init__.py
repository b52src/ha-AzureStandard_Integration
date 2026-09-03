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

# Read version from manifest.json once at module load — used as a cache-buster
# query string on the panel JS URL so browsers always fetch the latest file.
_VERSION = (
    __import__("json")
    .loads((pathlib.Path(__file__).parent / "manifest.json").read_text())
    .get("version", "0")
)

# Panel registration constants
_PANEL_JS         = "azure-standard-panel.js"
_PANEL_ELEMENT    = "azure-standard-panel"
_PANEL_TITLE      = "Azure Standard"
_PANEL_ICON       = "mdi:sprout"

# Lovelace resources — both JS files auto-registered so users don't need the
# manual "Settings → Dashboards → Resources" step.
_LOVELACE_RESOURCES = [
    {
        "url": "/azure_standard_panel/azure-standard-cutoff-card.js",
        "res_type": "module",
    },
    {
        "url": "/azure_standard_panel/azure-standard-panel.js",
        "res_type": "module",
    },
]

# hass.data key for tracking which resource IDs we registered.
_RESOURCE_IDS_KEY = f"{DOMAIN}_lovelace_resource_ids"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the www/ directory so HA serves the panel JS file."""
    www_path = pathlib.Path(__file__).parent / "www"
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path="/azure_standard_panel",
            path=str(www_path),
            cache_headers=False,
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
            module_url=f"/azure_standard_panel/{_PANEL_JS}?v={_VERSION}",
            sidebar_title=_PANEL_TITLE,
            sidebar_icon=_PANEL_ICON,
            require_admin=False,
            config={},
        )

    # Auto-register Lovelace resources (idempotent — only runs once across all
    # config entries for this domain; skipped if URLs are already registered).
    if _RESOURCE_IDS_KEY not in hass.data:
        await _async_register_lovelace_resources(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove the panel and deregister Lovelace resources when the last config
    # entry is unloaded.
    if not hass.data.get(DOMAIN):
        hass.components.frontend.async_remove_panel(DOMAIN)
        await _async_remove_lovelace_resources(hass)

    return unloaded


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Lovelace resource helpers
# ---------------------------------------------------------------------------

async def _async_register_lovelace_resources(hass: HomeAssistant) -> None:
    """Add the integration's JS files to Lovelace resources if not present.

    Uses the ``lovelace`` component's resource storage (HA 2022.12+). Any URL
    already registered (by a previous run or a manual addition) is skipped so
    this operation is idempotent.
    """
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None or not hasattr(lovelace, "resources"):
            _LOGGER.debug(
                "azure_standard: lovelace resources API not available — "
                "skipping auto-registration (user must add resources manually)"
            )
            return

        resources = lovelace.resources
        await resources.async_load(True)
        existing_urls: set[str] = {
            r["url"] for r in resources.async_items()
        }

        registered_ids: list[str] = []
        for res in _LOVELACE_RESOURCES:
            if res["url"] in existing_urls:
                _LOGGER.debug(
                    "azure_standard: Lovelace resource already registered: %s",
                    res["url"],
                )
                continue
            res_id = await resources.async_create_item(
                {"res_type": res["res_type"], "url": res["url"]}
            )
            registered_ids.append(res_id)
            _LOGGER.info(
                "azure_standard: Registered Lovelace resource: %s", res["url"]
            )

        # Store resource IDs so we can remove them on unload.
        hass.data[_RESOURCE_IDS_KEY] = registered_ids

    except Exception:  # noqa: BLE001
        _LOGGER.debug(
            "azure_standard: Could not auto-register Lovelace resources "
            "(non-fatal — resources can be added manually)",
            exc_info=True,
        )


async def _async_remove_lovelace_resources(hass: HomeAssistant) -> None:
    """Remove previously auto-registered Lovelace resources."""
    resource_ids: list[str] = hass.data.pop(_RESOURCE_IDS_KEY, [])
    if not resource_ids:
        return

    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None or not hasattr(lovelace, "resources"):
            return

        resources = lovelace.resources
        for res_id in resource_ids:
            try:
                await resources.async_delete_item(res_id)
                _LOGGER.info(
                    "azure_standard: Removed Lovelace resource id=%s", res_id
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "azure_standard: Could not remove Lovelace resource id=%s "
                    "(may have been removed manually)",
                    res_id,
                    exc_info=True,
                )
    except Exception:  # noqa: BLE001
        _LOGGER.debug(
            "azure_standard: Error removing Lovelace resources (non-fatal)",
            exc_info=True,
        )
