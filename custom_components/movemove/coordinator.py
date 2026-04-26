from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import logging
import random

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN
from .movemove_client import MoveMoveClient, MoveMoveCredentials, MoveMoveError

_LOGGER = logging.getLogger(__name__)
CACHE_VERSION = 1
MAX_BACKOFF_MULTIPLIER = 8
JITTER_MIN = 0.9
JITTER_MAX = 1.1


class MoveMoveDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
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
        self._entry_id = entry_id
        self._max_records = max_records
        self._base_update_interval = timedelta(minutes=scan_interval_minutes)
        self._store: Store[dict] = Store(hass, CACHE_VERSION, f"{DOMAIN}.{entry_id}")
        self._last_successful_data: dict | None = None
        self._last_success_at: str | None = None
        self._last_refresh_error: str | None = None
        self._last_refresh_attempt_at: str | None = None
        self._consecutive_failures = 0
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._base_update_interval,
        )

    async def async_initialize(self) -> None:
        stored = await self._store.async_load()
        if not stored:
            return

        data = stored.get("data")
        if not data:
            return

        self._last_successful_data = self._prepare_payload(data)
        self._last_success_at = stored.get("last_success_at")
        self.data = self._with_diagnostics(
            self._last_successful_data,
            stale=True,
            error="Using cached data while waiting for a fresh update",
        )

    def _prepare_payload(self, data: dict) -> dict:
        payload = deepcopy(data)
        payload["latestTransaction"] = payload.get("transactions", [None])[0] if payload.get("transactions") else None
        payload["latestFuelTransaction"] = next(
            (tx for tx in payload.get("transactions", []) if tx.get("typeId") == "FUEL"),
            None,
        )
        return payload

    def _with_diagnostics(self, data: dict, *, stale: bool, error: str | None) -> dict:
        payload = deepcopy(data)
        last_success_age_minutes = None
        if self._last_success_at:
            try:
                last_success_age_minutes = round(
                    (datetime.now(UTC) - datetime.fromisoformat(self._last_success_at)).total_seconds() / 60,
                    1,
                )
            except ValueError:
                last_success_age_minutes = None
        diagnostics = dict(payload.get("diagnostics") or {})
        diagnostics.update(
            {
                "usingCachedData": stale,
                "lastUpdateSuccessful": not stale,
                "lastSuccessfulUpdate": self._last_success_at,
                "lastSuccessfulUpdateAgeMinutes": last_success_age_minutes,
                "lastRefreshAttempt": self._last_refresh_attempt_at,
                "consecutiveFailures": self._consecutive_failures,
                "lastError": error,
                "nextRefreshIntervalSeconds": int(self.update_interval.total_seconds()),
            }
        )
        payload["diagnostics"] = diagnostics
        return payload

    def _set_update_interval(self, failures: int) -> None:
        multiplier = min(2**failures, MAX_BACKOFF_MULTIPLIER)
        jitter = random.uniform(JITTER_MIN, JITTER_MAX)
        interval_seconds = max(60, int(self._base_update_interval.total_seconds() * multiplier * jitter))
        self.update_interval = timedelta(seconds=interval_seconds)

    async def _persist_cache(self, data: dict) -> None:
        await self._store.async_save(
            {
                "last_success_at": self._last_success_at,
                "data": data,
            }
        )

    async def _async_update_data(self) -> dict:
        try:
            data, cache_to_persist = await self.hass.async_add_executor_job(self._fetch_data)
            if cache_to_persist is not None:
                await self._persist_cache(cache_to_persist)
            return data
        except MoveMoveError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected MoveMove error: {err}") from err

    def _fetch_data(self) -> tuple[dict, dict | None]:
        now = datetime.now(UTC)
        self._last_refresh_attempt_at = now.isoformat()
        try:
            data = self._client.fetch_month_data(now.year, now.month, max_records=self._max_records)
        except MoveMoveError as err:
            self._consecutive_failures += 1
            self._last_refresh_error = str(err)
            self._set_update_interval(self._consecutive_failures)
            if self._last_successful_data is not None:
                _LOGGER.warning(
                    "MoveMove update failed for entry %s; keeping last known data available (%s)",
                    self._entry_id,
                    err,
                )
                return self._with_diagnostics(self._last_successful_data, stale=True, error=str(err)), None
            raise

        data["currentPeriod"] = {"year": now.year, "month": now.month}
        data = self._prepare_payload(data)
        self._last_success_at = now.isoformat()
        self._last_refresh_error = None
        self._consecutive_failures = 0
        self._set_update_interval(0)
        self._last_successful_data = deepcopy(data)
        return self._with_diagnostics(data, stale=False, error=None), deepcopy(self._last_successful_data)
