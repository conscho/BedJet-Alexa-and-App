"""BedJet V3 BLE connection manager using bleak."""

import asyncio
import logging
from typing import Callable

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from bedjet_protocol import (
    BEDJET_ADVERTISEMENT_PREFIX,
    BEDJET_COMMAND_UUID,
    BEDJET_SERVICE_UUID,
    BEDJET_STATUS_UUID,
    BedjetButton,
    BedjetStatus,
    build_button_command,
    build_set_fan_command,
    build_set_runtime_command,
    build_set_temp_command,
    parse_status_packet,
)

logger = logging.getLogger(__name__)


class BedjetBLE:
    """Manages BLE connection to a BedJet V3 device."""

    def __init__(self):
        self._client: BleakClient | None = None
        self._device: BLEDevice | None = None
        self._status = BedjetStatus()
        self._status_callbacks: list[Callable[[BedjetStatus], None]] = []
        self._connected = False
        self._reconnect_task: asyncio.Task | None = None

    @property
    def status(self) -> BedjetStatus:
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None and self._client.is_connected

    def add_status_callback(self, callback: Callable[[BedjetStatus], None]):
        self._status_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[BedjetStatus], None]):
        self._status_callbacks.discard(callback) if hasattr(self._status_callbacks, 'discard') else None
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    async def scan(self, timeout: float = 10.0) -> list[BLEDevice]:
        """Scan for BedJet devices."""
        logger.info("Scanning for BedJet devices...")
        devices = await BleakScanner.discover(
            timeout=timeout,
            service_uuids=[BEDJET_SERVICE_UUID],
        )
        bedjet_devices = [
            d for d in devices
            if d.name and d.name.upper().startswith(BEDJET_ADVERTISEMENT_PREFIX)
        ]
        logger.info(f"Found {len(bedjet_devices)} BedJet device(s)")
        return bedjet_devices

    async def connect(self, address: str | None = None):
        """Connect to a BedJet device by address, or scan and connect to the first one found."""
        if self.is_connected:
            logger.info("Already connected")
            return

        if address:
            self._device = None
            self._client = BleakClient(address, disconnected_callback=self._on_disconnect)
        else:
            devices = await self.scan()
            if not devices:
                raise RuntimeError("No BedJet devices found")
            self._device = devices[0]
            logger.info(f"Connecting to {self._device.name} ({self._device.address})")
            self._client = BleakClient(self._device, disconnected_callback=self._on_disconnect)

        await self._client.connect()
        self._connected = True
        logger.info("Connected to BedJet")

        # Subscribe to status notifications
        await self._client.start_notify(BEDJET_STATUS_UUID, self._on_status_notification)
        logger.info("Subscribed to status notifications")

    async def disconnect(self):
        """Disconnect from the BedJet."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self._client and self._client.is_connected:
            await self._client.disconnect()
        self._connected = False
        self._status = BedjetStatus()
        logger.info("Disconnected from BedJet")

    def _on_disconnect(self, client: BleakClient):
        """Handle unexpected disconnection."""
        logger.warning("BedJet disconnected unexpectedly")
        self._connected = False
        self._status.is_connected = False
        self._notify_status()

        # Schedule reconnection
        loop = asyncio.get_event_loop()
        if loop.is_running():
            self._reconnect_task = loop.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        """Attempt to reconnect with exponential backoff."""
        delays = [2, 4, 8, 16, 30, 60]
        for attempt, delay in enumerate(delays):
            logger.info(f"Reconnection attempt {attempt + 1} in {delay}s...")
            await asyncio.sleep(delay)
            try:
                await self.connect(
                    address=self._device.address if self._device else None
                )
                logger.info("Reconnected successfully")
                return
            except Exception as e:
                logger.warning(f"Reconnection failed: {e}")

        # Keep trying every 60s
        while True:
            await asyncio.sleep(60)
            try:
                await self.connect(
                    address=self._device.address if self._device else None
                )
                logger.info("Reconnected successfully")
                return
            except Exception as e:
                logger.warning(f"Reconnection failed: {e}")

    def _on_status_notification(self, sender, data: bytearray):
        """Handle status notification from BedJet."""
        self._status = parse_status_packet(bytes(data))
        self._status.is_connected = True
        self._notify_status()

    def _notify_status(self):
        """Notify all registered callbacks of status change."""
        for callback in self._status_callbacks:
            try:
                callback(self._status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    async def _write_command(self, command: bytes):
        """Write a command to the BedJet."""
        if not self.is_connected:
            raise RuntimeError("Not connected to BedJet")
        await self._client.write_gatt_char(BEDJET_COMMAND_UUID, command)

    async def turn_off(self):
        await self._write_command(build_button_command(BedjetButton.OFF))

    async def set_mode_heat(self):
        await self._write_command(build_button_command(BedjetButton.HEAT))

    async def set_mode_cool(self):
        await self._write_command(build_button_command(BedjetButton.COOL))

    async def set_mode_turbo(self):
        await self._write_command(build_button_command(BedjetButton.TURBO))

    async def set_mode_dry(self):
        await self._write_command(build_button_command(BedjetButton.DRY))

    async def set_mode_extended_heat(self):
        await self._write_command(build_button_command(BedjetButton.EXTENDED_HEAT))

    async def set_preset(self, preset: int):
        """Set a memory preset (1-3)."""
        buttons = {1: BedjetButton.M1, 2: BedjetButton.M2, 3: BedjetButton.M3}
        if preset not in buttons:
            raise ValueError("Preset must be 1, 2, or 3")
        await self._write_command(build_button_command(buttons[preset]))

    async def set_temperature(self, temp_f: float):
        """Set target temperature in Fahrenheit."""
        await self._write_command(build_set_temp_command(temp_f))

    async def set_fan_speed(self, percent: int):
        """Set fan speed as percentage (5-100 in 5% steps)."""
        await self._write_command(build_set_fan_command(percent))

    async def set_runtime(self, hours: int, minutes: int):
        """Set remaining runtime."""
        await self._write_command(build_set_runtime_command(hours, minutes))
