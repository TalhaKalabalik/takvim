"""Config flow for the Fazilet Takvim integration."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN

CONF_DISTRICT_ID = "district_id"

API_BASE_URL = "https://backend.fazilettakvimi.com/content/public"
GERMANY_COUNTRY_ID = 14
GERMAN_LANGUAGE_ID = 4


class TakvimConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fazilet Takvim."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._cities: dict[str, str] = {}

    async def _async_get_json(
        self,
        endpoint: str,
        params: dict[str, int | str],
    ) -> Any:
        """Request JSON from the Fazilet API."""
        session = async_get_clientsession(self.hass)

        try:
            async with asyncio.timeout(10):
                async with session.get(
                    f"{API_BASE_URL}/{endpoint}",
                    params=params,
                ) as response:
                    response.raise_for_status()
                    return await response.json()

        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise CannotConnect from err

    async def _async_load_cities(self) -> None:
        """Load all German cities from the API."""
        if self._cities:
            return

        response = await self._async_get_json(
            "cities-by-country",
            {
                "districtId": GERMANY_COUNTRY_ID,
                "lang": GERMAN_LANGUAGE_ID,
            },
        )

        if not isinstance(response, list):
            raise CannotConnect

        cities: dict[str, str] = {}

        for item in response:
            if not isinstance(item, dict):
                continue

            city_id = str(item.get("id", ""))
            city_name = item.get("adi")

            if city_id.isdigit() and isinstance(city_name, str):
                city_name = city_name.strip()

                if city_name:
                    cities[city_id] = city_name

        if not cities:
            raise CannotConnect

        self._cities = cities

    async def _async_validate_city(self, city_id: str) -> None:
        """Validate the selected city using the daily endpoint."""
        response = await self._async_get_json(
            "daily",
            {
                "districtId": city_id,
                "lang": GERMAN_LANGUAGE_ID,
            },
        )

        if not isinstance(response, dict):
            raise InvalidCity

        form = response.get("form")

        if not isinstance(form, dict):
            raise InvalidCity

        if str(form.get("sehir_id")) != city_id:
            raise InvalidCity

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user select a city."""
        errors: dict[str, str] = {}

        try:
            await self._async_load_cities()
        except CannotConnect:
            errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            city_id = str(user_input[CONF_DISTRICT_ID])
            city_name = self._cities.get(city_id)

            if city_name is None:
                errors["base"] = "invalid_city"
            else:
                try:
                    await self._async_validate_city(city_id)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidCity:
                    errors["base"] = "invalid_city"
                else:
                    await self.async_set_unique_id(city_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=city_name,
                        data={
                            CONF_DISTRICT_ID: int(city_id),
                        },
                    )

        options = [
            SelectOptionDict(value=city_id, label=city_name)
            for city_id, city_name in sorted(
                self._cities.items(),
                key=lambda item: item[1].casefold(),
            )
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_DISTRICT_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate that the API cannot be reached."""


class InvalidCity(HomeAssistantError):
    """Error to indicate that the selected city is invalid."""