"""Config flow for Panasonic Aquarea integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aioaquarea import Client, AquareaEnvironment
from aioaquarea.errors import AuthenticationError, ClientError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Panasonic Aquarea."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)

    client = Client(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        session=session,
        device_direct=True,
        refresh_login=True,
        environment=AquareaEnvironment.PRODUCTION,
    )

    try:
        devices = await client.get_devices()
        if not devices:
            raise CannotConnect("No devices found")
    except AuthenticationError as err:
        _LOGGER.error("Authentication failed: %s", err)
        raise InvalidAuth from err
    except ClientError as err:
        _LOGGER.error("Client error: %s", err)
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {"title": f"Panasonic Aquarea ({len(devices)} devices)"}