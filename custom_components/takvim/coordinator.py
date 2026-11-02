"""Coordinator for the Takvim prayer times integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, DOMAIN, PRAYERS

_LOGGER = logging.getLogger(__name__)
_LOCAL_TIME_ZONE = ZoneInfo("Europe/Berlin")


class PrayerTimesCoordinator(DataUpdateCoordinator):
    """Coordinator for retrieving Takvim prayer times."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        district_id: int,
    ) -> None:
        """Initialize the coordinator."""
        self.district_id = district_id

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(hours=12),
        )

    async def _async_update_data(self) -> dict[str, datetime]:
        """Fetch prayer time data from the API."""
        session = async_get_clientsession(self.hass)

        try:
            async with asyncio.timeout(10):
                async with session.get(
                    API_URL,
                    params={"districtId": self.district_id, "lang": 1},
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

            if not isinstance(data, dict):
                raise ValueError("The API response is not an object")

            days = data.get("vakitler")
            if not isinstance(days, list):
                raise ValueError("The API response does not contain prayer days")

            today = datetime.now(_LOCAL_TIME_ZONE).date().isoformat()
            day_data = next(
                (
                    day
                    for day in days
                    if isinstance(day, dict) and day.get("tarih") == today
                ),
                None,
            )

            if day_data is None:
                raise UpdateFailed(f"No prayer times found for {today}")

            result = {
                prayer: self._make_timestamp(day_data[prayer][0]["tarih"])
                for prayer in PRAYERS
            }

        except UpdateFailed:
            raise
        except (
            TimeoutError,
            aiohttp.ClientError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as err:
            raise UpdateFailed(f"Error fetching prayer times: {err}") from err

        _LOGGER.debug("Prayer times for %s: %s", today, result)
        return result

    def _make_timestamp(self, time_string: str) -> datetime:
        """Convert an API ISO timestamp to a timezone-aware datetime."""
        if not isinstance(time_string, str):
            raise ValueError("The prayer time is not a string")

        clean = time_string.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
