"""Base entity class for the Azure Standard integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class AzureStandardEntity(CoordinatorEntity):
    """Base class for all Azure Standard entities.

    Subclasses inherit the coordinator-driven update cycle and share a
    single *Azure Standard* device grouping in the HA device registry.
    Product-specific entities override :attr:`_attr_device_info` to
    create one device per tracked product.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        """Initialise the entity and register it with the coordinator."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="Azure Standard",
            manufacturer="Azure Standard",
            model="Co-op Delivery",
            configuration_url="https://www.azurestandard.com",
        )
