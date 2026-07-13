"""Config flow for Delta Energy."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AVERAGING_WINDOW,
    CONF_END_ATTRIBUTE,
    CONF_SOURCE_ENTITY,
    CONF_START_ATTRIBUTE,
    DEFAULT_AVERAGING_WINDOW,
    DEFAULT_END_ATTRIBUTE,
    DEFAULT_START_ATTRIBUTE,
    DOMAIN,
)


class DeltaEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Delta Energy."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_SOURCE_ENTITY])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Delta Energy"): str,
                vol.Required(CONF_SOURCE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_START_ATTRIBUTE,
                    default=DEFAULT_START_ATTRIBUTE,
                ): str,
                vol.Required(
                    CONF_END_ATTRIBUTE,
                    default=DEFAULT_END_ATTRIBUTE,
                ): str,
                vol.Required(
                    CONF_AVERAGING_WINDOW,
                    default=DEFAULT_AVERAGING_WINDOW,
                ): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create the options flow."""
        return DeltaEnergyOptionsFlow(config_entry)


class DeltaEnergyOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Delta Energy."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage Delta Energy options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_start_attribute = self._config_entry.options.get(
            CONF_START_ATTRIBUTE,
            self._config_entry.data.get(
                CONF_START_ATTRIBUTE,
                DEFAULT_START_ATTRIBUTE,
            ),
        )
        current_end_attribute = self._config_entry.options.get(
            CONF_END_ATTRIBUTE,
            self._config_entry.data.get(
                CONF_END_ATTRIBUTE,
                DEFAULT_END_ATTRIBUTE,
            ),
        )
        current_averaging_window = self._config_entry.options.get(
            CONF_AVERAGING_WINDOW,
            self._config_entry.data.get(
                CONF_AVERAGING_WINDOW,
                DEFAULT_AVERAGING_WINDOW,
            ),
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_START_ATTRIBUTE,
                    default=current_start_attribute,
                ): str,
                vol.Required(
                    CONF_END_ATTRIBUTE,
                    default=current_end_attribute,
                ): str,
                vol.Required(
                    CONF_AVERAGING_WINDOW,
                    default=current_averaging_window,
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
