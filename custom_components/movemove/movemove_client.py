from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor


class MoveMoveError(Exception):
    """Raised when communicating with MoveMove fails."""


@dataclass(slots=True)
class MoveMoveCredentials:
    username: str
    password: str
    csrf_token: str | None = None


class MoveMoveClient:
    """Small synchronous client used by the Home Assistant coordinator.

    Note: The exact upstream API is not officially documented. The client tries
    common endpoint paths used by the OnTheMove backend and raises a
    MoveMoveError with context if none work.
    """

    _BASE_URL = "https://outsystems.mtc.nl"
    _LOGIN_PATHS = (
        "/OnTheMove/moduleservices/accountsrestservice/login",
        "/OnTheMove/moduleservices/AccountsRESTService/Login",
    )
    _MONTH_PATHS = (
        "/OnTheMove/moduleservices/movemoverestservice/monthoverview",
        "/OnTheMove/moduleservices/MoveMoveRESTService/MonthOverview",
    )

    def __init__(self, credentials: MoveMoveCredentials) -> None:
        self._credentials = credentials
        self._opener = build_opener(HTTPCookieProcessor())
        self._logged_in = False

    def login(self) -> None:
        payload = {
            "username": self._credentials.username,
            "password": self._credentials.password,
        }
        if self._credentials.csrf_token:
            payload["csrfToken"] = self._credentials.csrf_token

        last_error: Exception | None = None
        for path in self._LOGIN_PATHS:
            try:
                response = self._request_json("POST", path, payload)
            except MoveMoveError as err:
                last_error = err
                continue

            if isinstance(response, dict) and response.get("success") is False:
                raise MoveMoveError(response.get("message", "Invalid Login"))

            self._logged_in = True
            return

        raise MoveMoveError(f"Unable to login to MoveMove: {last_error}")

    def fetch_month_data(self, year: int, month: int, *, max_records: int = 100) -> dict:
        if not self._logged_in:
            self.login()

        params = {"year": year, "month": month, "maxRecords": max_records}

        last_error: Exception | None = None
        for path in self._MONTH_PATHS:
            try:
                response = self._request_json("GET", path, params)
            except MoveMoveError as err:
                last_error = err
                continue

            if not isinstance(response, dict):
                raise MoveMoveError("Unexpected response from MoveMove month endpoint")

            return {
                "summary": response.get("summary", response),
                "transactions": response.get("transactions", []),
            }

        raise MoveMoveError(f"Unable to fetch MoveMove month data: {last_error}")

    def _request_json(self, method: str, path: str, data: dict) -> dict | list:
        url = f"{self._BASE_URL}{path}"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "HomeAssistant-MoveMove/0.1",
        }

        body: bytes | None = None
        if method == "GET":
            query = urlencode(data)
            url = f"{url}?{query}"
        else:
            body = json.dumps(data).encode("utf-8")

        req = Request(url, headers=headers, method=method, data=body)
        try:
            with self._opener.open(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except HTTPError as err:
            details = err.read().decode("utf-8", errors="ignore")
            raise MoveMoveError(f"HTTP {err.code} for {path}: {details}") from err
        except URLError as err:
            raise MoveMoveError(f"Connection error for {path}: {err}") from err
        except json.JSONDecodeError as err:
            raise MoveMoveError(f"Invalid JSON response for {path}") from err
