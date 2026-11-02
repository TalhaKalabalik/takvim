"""The Takvim integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .coordinator import PrayerTimesCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Takvim from a config entry."""
    coordinator = PrayerTimesCoordinator(
        hass,
        entry,
        entry.data["district_id"],
    )

    # Initial fetch when Home Assistant starts
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def _async_daily_refresh(_: datetime) -> None:
        """Refresh prayer times shortly after the local day changes."""
        if not entry.pref_disable_polling:
            await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(
            hass,
            _async_daily_refresh,
            hour=0,
            minute=5,
            second=0,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if success:
        hass.data[DOMAIN].pop(entry.entry_id)
    return success
