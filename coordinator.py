from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN
from .movemove_client import MoveMoveClient, MoveMoveCredentials, MoveMoveError

_LOGGER = logging.getLogger(__name__)


class MoveMoveDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        username: str,
        password: str,
        csrf_token: str | None,
        max_records: int,
        scan_interval_minutes: int = DEFAULT_SCAN_INTERVAL_MINUTES,
    ) -> None:
        self._client = MoveMoveClient(
            MoveMoveCredentials(
                username=username,
                password=password,
                csrf_token=csrf_token,
            )
        )
        self._max_records = max_records
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except MoveMoveError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected MoveMove error: {err}") from err

    def _fetch_data(self) -> dict:
        now = datetime.now(UTC)
        data = self._client.fetch_month_data(now.year, now.month, max_records=self._max_records)
        data["currentPeriod"] = {"year": now.year, "month": now.month}
        data["latestTransaction"] = data.get("transactions", [None])[0] if data.get("transactions") else None
        return data
