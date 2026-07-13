"""Sensor platform for Delta Energy."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_AVERAGING_WINDOW,
    CONF_END_ATTRIBUTE,
    CONF_SOURCE_ENTITY,
    CONF_START_ATTRIBUTE,
    DEFAULT_AVERAGING_WINDOW,
    DOMAIN,
)


@dataclass
class DeltaSample:
    """One delta energy sample."""

    start_key: int
    end_key: int
    delta_kwh: float
    seconds: int


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Delta Energy sensors."""
    async_add_entities(
        [
            DeltaTotalEnergySensor(hass, entry),
            DeltaAveragePowerSensor(hass, entry),
        ]
    )


class DeltaEnergyBaseSensor(SensorEntity):
    """Base class for delta energy sensors."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize base sensor."""
        self.hass = hass
        self.entry = entry

        self._source_entity = entry.data[CONF_SOURCE_ENTITY]
        self._start_attribute = entry.options.get(
            CONF_START_ATTRIBUTE,
            entry.data[CONF_START_ATTRIBUTE],
        )
        self._end_attribute = entry.options.get(
            CONF_END_ATTRIBUTE,
            entry.data[CONF_END_ATTRIBUTE],
        )

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
        }

        self._unsub_state = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to source sensor changes."""
        self._unsub_state = async_track_state_change_event(
            self.hass,
            [self._source_entity],
            self._async_source_changed,
        )

        state = self.hass.states.get(self._source_entity)
        if state is not None and self._process_source_state(state):
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from source sensor changes."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None

    @callback
    def _async_source_changed(self, event: Event) -> None:
        """Handle source sensor state change."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if self._process_source_state(new_state):
            self.async_write_ha_state()

    def _read_sample(self, state: State) -> DeltaSample | None:
        """Read delta sample from source state and attributes."""
        try:
            delta_kwh = float(state.state)
            start_key = int(state.attributes[self._start_attribute])
            end_key = int(state.attributes[self._end_attribute])
        except (KeyError, TypeError, ValueError):
            return None

        seconds = end_key - start_key
        if seconds <= 0:
            return None

        return DeltaSample(
            start_key=start_key,
            end_key=end_key,
            delta_kwh=delta_kwh,
            seconds=seconds,
        )

    def _process_source_state(self, state: State) -> bool:
        """Process source state. Implemented by subclasses."""
        raise NotImplementedError


class DeltaTotalEnergySensor(DeltaEnergyBaseSensor, RestoreEntity):
    """Accumulated total energy from delta energy values."""

    _attr_name = "Total energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize total energy sensor."""
        super().__init__(hass, entry)

        self._attr_unique_id = f"{entry.entry_id}_total_energy"

        self._total = 0.0
        self._last_processed_key: int | None = None
        self._counted_for_key = 0.0

    async def async_added_to_hass(self) -> None:
        """Restore previous total and subscribe to source changes."""
        last_state = await self.async_get_last_state()

        if last_state is not None:
            try:
                self._total = float(last_state.state)
            except (TypeError, ValueError):
                self._total = 0.0

            try:
                last_processed_key = last_state.attributes.get("last_processed_key")
                self._last_processed_key = (
                    int(last_processed_key)
                    if last_processed_key is not None
                    else None
                )
            except (TypeError, ValueError):
                self._last_processed_key = None

            try:
                self._counted_for_key = float(
                    last_state.attributes.get("counted_for_key", 0)
                )
            except (TypeError, ValueError):
                self._counted_for_key = 0.0

        await super().async_added_to_hass()

    @property
    def native_value(self) -> float:
        """Return total energy."""
        return round(self._total, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            "source_entity": self._source_entity,
            "start_attribute": self._start_attribute,
            "end_attribute": self._end_attribute,
            "last_processed_key": self._last_processed_key,
            "counted_for_key": self._counted_for_key,
        }

    def _process_source_state(self, state: State) -> bool:
        """Process source delta for total energy."""
        sample = self._read_sample(state)
        if sample is None:
            return False

        if sample.end_key != self._last_processed_key:
            self._last_processed_key = sample.end_key
            self._counted_for_key = 0.0

        if sample.delta_kwh > self._counted_for_key:
            self._total += sample.delta_kwh - self._counted_for_key
            self._counted_for_key = sample.delta_kwh
            return True

        return False


class DeltaAveragePowerSensor(DeltaEnergyBaseSensor):
    """Average power from delta energy values."""

    _attr_name = "Average power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize average power sensor."""
        super().__init__(hass, entry)

        self._attr_unique_id = f"{entry.entry_id}_average_power"

        self._averaging_window = int(
            entry.options.get(
                CONF_AVERAGING_WINDOW,
                entry.data.get(CONF_AVERAGING_WINDOW, DEFAULT_AVERAGING_WINDOW),
            )
        )

        self._samples: deque[DeltaSample] = deque()
        self._last_processed_key: int | None = None
        self._power: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return average power."""
        return self._power

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            "source_entity": self._source_entity,
            "start_attribute": self._start_attribute,
            "end_attribute": self._end_attribute,
            "averaging_window": self._averaging_window,
            "samples": len(self._samples),
            "last_processed_key": self._last_processed_key,
        }

    def _process_source_state(self, state: State) -> bool:
        """Process source delta for average power."""
        sample = self._read_sample(state)
        if sample is None:
            return False

        if sample.end_key == self._last_processed_key:
            return False

        self._last_processed_key = sample.end_key
        self._samples.append(sample)

        if self._averaging_window > 0:
            cutoff = sample.end_key - self._averaging_window
            while self._samples and self._samples[0].end_key <= cutoff:
                self._samples.popleft()
        else:
            while len(self._samples) > 1:
                self._samples.popleft()

        total_delta = sum(item.delta_kwh for item in self._samples)
        total_seconds = sum(item.seconds for item in self._samples)

        if total_seconds <= 0:
            self._power = None
        else:
            self._power = round(total_delta * 3_600_000 / total_seconds, 1)

        return True
