#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# File: toonlib.py
"""All helper objects will live here"""

import json
import logging

import requests

from dataclasses import dataclass

__author__ = '''Costas Tyfoxylos <costas.tyf@gmail.com>'''
__docformat__ = 'plaintext'
__date__ = '''13-03-2017'''

LOGGER_BASENAME = '''helpers'''
LOGGER = logging.getLogger(LOGGER_BASENAME)
LOGGER.addHandler(logging.NullHandler())


@dataclass
class Token:
    """Models the token received from the service"""

    access_token: str
    refresh_token_expires_in: int
    expires_in: int
    refresh_token: str


@dataclass
class User:
    """Models the user"""

    client_id: str
    client_secret: str
    username: str
    password: str


@dataclass
class Agreement:
    """Models the agreement of the service"""

    id: str
    checksum: str
    heating_type: str
    display_common_name: str
    display_hardware_version: str
    display_software_version: str
    solar: bool
    toonly: bool


@dataclass
class ThermostatState:
    """Models the thermostat state"""

    name: str
    id: int
    temperature: int
    dhw: int


@dataclass
class ThermostatInfo:
    """Models the thermostat information"""

    active_state: int
    boiler_connected: int
    burner_info: str
    current_displayed_temperature: int
    current_modulation_level: int
    current_set_point: int
    error_found: int
    have_ot_boiler: int
    next_program: int
    next_set_point: int
    next_state: int
    next_time: int
    ot_communication_error: str
    program_state: int
    real_set_point: str


@dataclass
class Usage:
    """Models the core usage object"""

    average_daily: int
    average: int
    daily_cost: int
    daily_usage: int
    is_smart: int
    meter_reading: int
    value: int


@dataclass
class PowerUsage(Usage):
    """Models the power usage object"""

    meter_reading_low: int
    daily_usage_low: int


@dataclass
class Solar:
    """Models the solar object"""

    maximum: int
    produced: int
    value: int
    average_produced: int
    meter_reading_low_produced: int
    meter_reading_produced: int
    daily_cost_produced: int


@dataclass
class SmokeDetector:
    """Models the smokedeterctors"""

    device_uuid: str
    name: str
    last_connected_change: int
    is_connected: int
    battery_level: int
    device_type: str


class Switch:
    """Core object to implement the turning on, off or toggle

    Both hue lamps and fibaro plugs have a switch component that is shared.
    This implements that usage.
    """

    def __init__(self, toon_instance, name):
        logger_name = u'{base}.{suffix}'.format(base=LOGGER_BASENAME,
                                                suffix=self.__class__.__name__)
        self._logger = logging.getLogger(logger_name)
        self.toon = toon_instance
        self._name = name
        self._device_type = None
        self._zwave_index = None
        self._zwave_uuid = None
        self._device_uuid = None

    @property
    def name(self):
        """The name of the device"""
        return self._name

    def _get_value(self, name, config=False):
        key = 'deviceConfigInfo' if config else 'deviceStatusInfo'
        return next((item.get(name) for item in
                     self.toon.status.get(key).get('device')  # noqa
                     if item.get('name') == self.name), None)

    def toggle(self):
        """Toggles the status of the device"""
        return self._change_state(not self.current_state)

    def turn_on(self):
        """Turns the device on"""
        return self._change_state(1)

    @property
    def status(self):
        """Returns the status of the device in a human friendly way"""
        return 'on' if self.current_state else 'off'

    def _change_state(self, state):
        if not self.can_toggle:  # pylint: disable=no-else-return
            self._logger.warning('The item is not connected or locked, cannot '
                                 'change state.')
            return False
        else:
            url = '{api_url}/devices/{id}'.format(api_url=self.toon._api_url,  # pylint: disable=protected-access
                                                  id=self.device_uuid)
            data = requests.get(url, headers=self.toon._headers).json()  # pylint: disable=protected-access
            data["currentState"] = int(state)
            response = requests.put(url,
                                    data=json.dumps(data),
                                    headers=self.toon._headers)  # pylint: disable=protected-access
            self._logger.debug('Response received {}'.format(response.content))
            self.toon._clear_cache()  # noqa
            return True

    @property
    def can_toggle(self):
        """Boolean about the capability of the device to toggle state"""
        return False if not self.is_connected or self.is_locked else True

    def turn_off(self):
        """Turns the device off"""
        return self._change_state(0)

    @property
    def device_uuid(self):
        """The uuid of the device"""
        if not self._device_uuid:
            self._device_uuid = self._get_value('devUUID')
        return self._device_uuid

    @property
    def is_connected(self):
        """Boolean about the connection status of the device"""
        value = self._get_value('isConnected')
        return True if value else False

    @property
    def current_state(self):
        """The device's current state"""
        return self._get_value('currentState')

    @property
    def device_type(self):
        """The type of the device"""
        if not self._device_type:
            self._device_type = self._get_value('devType', config=True)
        return self._device_type

    @property
    def in_switch_all_group(self):
        """Boolean about whether the device is in a switch group"""
        value = self._get_value('inSwitchAll', config=True)
        return True if value else False

    @property
    def in_switch_schedule(self):
        """Boolean about whether the device is in a switch schedule"""
        value = self._get_value('inSwitchSchedule', config=True)
        return True if value else False

    @property
    def zwave_index(self):
        """The zwave index of the device"""
        if not self._zwave_index:
            self._zwave_index = self._get_value('position', config=True)
        return self._zwave_index

    @property
    def is_locked(self):
        """Boolean about the lock state of the object"""
        value = self._get_value('switchLocked', config=True)
        return True if value else False

    @property
    def zwave_uuid(self):
        """The zwave uuid"""
        if not self._zwave_uuid:
            self._zwave_uuid = self._get_value('zwUuid', config=True)
        return self._zwave_uuid


class SmartPlug(Switch):
    """Object modeling the fibaro smart plugs the toon can interact with.

    It inherits from switch which is the common interface with the hue
    lamps to turn on, off or toggle
    """

    def __init__(self, toon_instance, name):
        super(SmartPlug, self).__init__(toon_instance, name)
        self._usage_capable = None

    @property
    def average_usage(self):
        """The average power usage"""
        return self._get_value('avgUsage') if self.usage_capable else 0

    @property
    def current_usage(self):
        """The current power usage"""
        return self._get_value('currentUsage') if self.usage_capable else 0

    @property
    def daily_usage(self):
        """The daily power usage"""
        return self._get_value('dayUsage') if self.usage_capable else 0

    @property
    def network_health_state(self):
        """The state of the network health"""
        return self._get_value('networkHealthState')

    @property
    def usage_capable(self):
        """Boolean about the capability of the device to report power usage"""
        if self._usage_capable is None:
            value = self._get_value('usageCapable', config=True)
            self._usage_capable = True if value else False
        return self._usage_capable

    @property
    def quantity_graph_uuid(self):
        """The uuid of the quantity graph"""
        return self._get_value('quantityGraphUuid', config=True)

    @property
    def flow_graph_uuid(self):
        """The uuid of the flow graph"""
        return self._get_value('flowGraphUuid', config=True)


class Light(Switch):
    """Object modeling the hue light bulbs that toon can interact with.

    It inherits from switch which is the common interface with the hue
    lamps to turn on, off or toggle
    """

    @property
    def rgb_color(self):
        """The rgb color value of the light"""
        return self._get_value('rgbColor')
