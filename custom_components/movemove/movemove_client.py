from __future__ import annotations

import logging
import json
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://outsystems.mtc.nl/OnTheMove"
LOGIN_PAGE_URL = f"{BASE_URL}/Login"
LOGIN_ACTION_URL = f"{BASE_URL}/screenservices/OtmAcc_Account/ActionAppLogin"
DEVICE_LOGIN_ACTION_URL = f"{BASE_URL}/screenservices/OtmDevice_DeviceLogin/ActionCheckAndRegisterNewDeviceLogin_Server"
TRANSACTIONS_ACTION_URL = f"{BASE_URL}/screenservices/OtmTrx_Transactions/Screen/Overview/DataActionGetTransactions"
TOTALS_ACTION_URL = f"{BASE_URL}/screenservices/OtmTrx_Transactions/OverviewDetailBlocks/TransactionTypeFilter/DataActionGetTotals"
MODULEINFO_URL = f"{BASE_URL}/moduleservices/moduleinfo"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RECORDS = 100
HEADLESS_CHROME_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) HeadlessChrome/147.0.7727.15 Safari/537.36"
)
DEFAULT_DEVICE_INFO = {
    "DeviceId": "",
    "DeviceManufacturer": "",
    "DeviceModel": "",
    "DesktopBrowser": "chrome",
    "OperatingSystem": "unknown",
    "UserAgent": HEADLESS_CHROME_UA,
    "IsMobileDevice": False,
}


class MoveMoveError(Exception):
    """Base exception for MoveMove client failures."""


@dataclass(frozen=True)
class ApiVersions:
    module_version: str
    login_api_version: str
    device_login_api_version: str
    transactions_api_version: str
    totals_api_version: str


@dataclass(frozen=True)
class MonthWindow:
    year: int
    month: int
    start_iso: str
    end_iso: str
    legacy_input_parameter_string: str


@dataclass(frozen=True)
class MoveMoveCredentials:
    username: str
    password: str
    csrf_token: str | None = None
    keep_me_logged_in: bool = True


def round_value(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def to_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_iso(dt: str) -> datetime:
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def month_window(year: int, month: int) -> MonthWindow:
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    end_dt = next_month - timedelta(seconds=1)
    return MonthWindow(
        year=year,
        month=month,
        start_iso=start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        end_iso=end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        legacy_input_parameter_string=(
            f"{start_dt.strftime('%Y-%m-%d 00:00:00')}"
            f"{end_dt.strftime('%Y-%m-%d 23:59:59')}0"
        ),
    )


class MoveMoveClient:
    def __init__(
        self,
        credentials: MoveMoveCredentials,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self.credentials = credentials
        self.timeout = timeout
        self.session = session or requests.Session()
        self._last_csrf_token: str | None = credentials.csrf_token
        self.versions: ApiVersions | None = None

    def _request(self, method: str, url: str, *, raise_for_status: bool = True, **kwargs: Any) -> requests.Response:
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as err:
            _LOGGER.exception("MoveMove request failed: %s %s", method.upper(), url)
            raise MoveMoveError(f"Request failed for {url}: {err}") from err

        if raise_for_status:
            self._raise_for_status(response, method, url)
        return response

    def _raise_for_status(self, response: requests.Response, method: str, url: str) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            body = response.text[:500].replace("\n", " ")
            message = self._response_exception_message(response)
            _LOGGER.error(
                "MoveMove HTTP error: %s %s -> %s, body=%s",
                method.upper(),
                url,
                response.status_code,
                body,
            )
            raise MoveMoveError(message or f"HTTP {response.status_code} for {url}") from err

    def _response_exception_message(self, response: requests.Response) -> str | None:
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            return None
        exception = payload.get("exception")
        if isinstance(exception, dict):
            return exception.get("message") or str(exception)
        return None

    def _parse_json_response(self, response: requests.Response, url: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as err:
            body = response.text[:500].replace("\n", " ")
            _LOGGER.error("MoveMove returned invalid JSON for %s, body=%s", url, body)
            raise MoveMoveError(f"Invalid JSON response from {url}") from err

        if data.get("exception"):
            message = data["exception"].get("message") or str(data["exception"])
            _LOGGER.error("MoveMove API exception for %s: %s", url, message)
            raise MoveMoveError(message)
        return data

    def _discover_versions(self) -> ApiVersions:
        moduleinfo = self._request("GET", MODULEINFO_URL)
        manifest = self._parse_json_response(moduleinfo, MODULEINFO_URL)["manifest"]
        module_version = manifest["versionToken"]
        url_versions = manifest["urlVersions"]

        def extract_api_version(path: str, marker: str) -> str:
            manifest_path = f"/OnTheMove{path}"
            script_url = f"{BASE_URL}{path}{url_versions[manifest_path]}"
            js = self._request("GET", script_url)
            text = js.text
            start = text.find(marker)
            if start == -1:
                _LOGGER.error("MoveMove API version marker not found in %s", script_url)
                raise MoveMoveError(f"Could not find API version marker in {path}")
            start += len(marker)
            end = text.find('"', start)
            return text[start:end]

        return ApiVersions(
            module_version=module_version,
            login_api_version=extract_api_version(
                "/scripts/OtmAcc_Account.controller.js",
                'callServerAction("AppLogin", "screenservices/OtmAcc_Account/ActionAppLogin", "',
            ),
            device_login_api_version=extract_api_version(
                "/scripts/OtmDevice_DeviceLogin.controller.js",
                'callServerAction("CheckAndRegisterNewDeviceLogin_Server", "screenservices/OtmDevice_DeviceLogin/ActionCheckAndRegisterNewDeviceLogin_Server", "',
            ),
            transactions_api_version=extract_api_version(
                "/scripts/OtmTrx_Transactions.Screen.Overview.mvc.js",
                'callDataAction("DataActionGetTransactions", "screenservices/OtmTrx_Transactions/Screen/Overview/DataActionGetTransactions", "',
            ),
            totals_api_version=extract_api_version(
                "/scripts/OtmTrx_Transactions.OverviewDetailBlocks.TransactionTypeFilter.mvc.js",
                'callDataAction("DataActionGetTotals", "screenservices/OtmTrx_Transactions/OverviewDetailBlocks/TransactionTypeFilter/DataActionGetTotals", "',
            ),
        )

    def _ensure_versions(self) -> ApiVersions:
        if self.versions is None:
            self.versions = self._discover_versions()
        return self.versions

    def _prime_login_page(self) -> None:
        response = self._request("GET", LOGIN_PAGE_URL, raise_for_status=False)
        self._raise_for_status(response, "GET", LOGIN_PAGE_URL)
        try:
            self._refresh_csrf_from_cookies(log_missing=False)
        except MoveMoveError:
            _LOGGER.debug("MoveMove login page loaded but no CSRF cookie was found yet")

    def _csrf_token(self, *, log_missing: bool = True) -> str:
        nr2 = self.session.cookies.get("nr2Users")
        if nr2 and "crf%3d" in nr2:
            part = nr2.split("crf%3d", 1)[1].split("%3b", 1)[0]
            token = urllib.parse.unquote(part).rstrip(";")
            self._last_csrf_token = token
            return token
        if self._last_csrf_token:
            return self._last_csrf_token
        if log_missing:
            _LOGGER.error("MoveMove CSRF token missing from session cookies")
        raise MoveMoveError("No CSRF token found in session cookies")

    def _base_headers(self, referer: str) -> dict[str, str]:
        headers = {
            "accept": "application/json",
            "content-type": "application/json; charset=UTF-8",
            "referer": referer,
            "user-agent": HEADLESS_CHROME_UA,
        }
        token = self._last_csrf_token
        if token:
            headers["x-csrftoken"] = token
        return headers

    def _refresh_csrf_from_cookies(self, *, log_missing: bool = True) -> None:
        self._last_csrf_token = self._csrf_token(log_missing=log_missing)

    def _build_login_payload(self) -> dict[str, Any]:
        versions = self._ensure_versions()
        return {
            "versionInfo": {
                "moduleVersion": versions.module_version,
                "apiVersion": versions.login_api_version,
            },
            "viewName": "Common.Login",
            "inputParameters": {
                "Username": self.credentials.username,
                "Password": self.credentials.password,
                "KeepMeLoggedIn": self.credentials.keep_me_logged_in,
            },
        }

    def _login_request(self) -> requests.Response:
        headers = self._base_headers(LOGIN_PAGE_URL)
        return self._request(
            "POST",
            LOGIN_ACTION_URL,
            raise_for_status=False,
            headers=headers,
            json=self._build_login_payload(),
        )

    def _reset_auth_state(self, *, rediscover_versions: bool = False, preserve_token: bool = True) -> None:
        previous_token = self._last_csrf_token
        self.session.cookies.clear()
        self._last_csrf_token = previous_token if preserve_token and previous_token else self.credentials.csrf_token
        if rediscover_versions:
            self.versions = None

    def _post_json(self, url: str, payload: dict[str, Any], referer: str) -> dict[str, Any]:
        response = self._request(
            "POST",
            url,
            raise_for_status=False,
            headers=self._base_headers(referer),
            json=payload,
        )

        if response.status_code == 403 and url != LOGIN_ACTION_URL:
            _LOGGER.warning("MoveMove returned 403 for %s, re-authenticating and retrying", url)
            self._reset_auth_state(rediscover_versions=True)
            self.login()
            response = self._request(
                "POST",
                url,
                raise_for_status=False,
                headers=self._base_headers(referer),
                json=payload,
            )

        self._raise_for_status(response, "POST", url)
        data = self._parse_json_response(response, url)
        self._refresh_csrf_from_cookies()
        return data

    def login(self) -> dict[str, Any]:
        self._ensure_versions()
        if not self._last_csrf_token:
            self._prime_login_page()

        response = self._login_request()

        if response.status_code == 403:
            _LOGGER.info("MoveMove login returned 403, refreshing CSRF token and retrying")
            self._reset_auth_state(rediscover_versions=True, preserve_token=False)
            self._prime_login_page()
            response = self._login_request()

        self._raise_for_status(response, "POST", LOGIN_ACTION_URL)
        data = self._parse_json_response(response, LOGIN_ACTION_URL)
        if not data.get("data", {}).get("Result"):
            _LOGGER.error("MoveMove login failed without API exception for username=%s", self.credentials.username)
            raise MoveMoveError("Login failed")

        self._refresh_csrf_from_cookies()
        self.register_device_login()
        return data["data"]

    def register_device_login(self, is_movemove: bool = False) -> None:
        versions = self._ensure_versions()
        payload = {
            "versionInfo": {
                "moduleVersion": versions.module_version,
                "apiVersion": versions.device_login_api_version,
            },
            "viewName": "Common.Login",
            "inputParameters": {
                "DeviceInfo": DEFAULT_DEVICE_INFO,
                "IsMoveMove": is_movemove,
            },
        }
        self._post_json(DEVICE_LOGIN_ACTION_URL, payload, LOGIN_PAGE_URL)

    def fetch_transactions(self, year: int, month: int, max_records: int = DEFAULT_MAX_RECORDS) -> list[dict[str, Any]]:
        versions = self._ensure_versions()
        window = month_window(year, month)
        payload = {
            "versionInfo": {
                "moduleVersion": versions.module_version,
                "apiVersion": versions.transactions_api_version,
            },
            "viewName": "MainFlow.Transactions",
            "screenData": {
                "variables": {
                    "ShowSharePopup": False,
                    "InputParameterString": window.legacy_input_parameter_string,
                    "MaxRecords": max_records,
                    "IsFirstLoad": True,
                    "IsLoadMore": False,
                    "PopupValues": {
                        "IconClassName": "",
                        "Title": "",
                        "Content": "",
                        "ButtonText": "",
                        "ButtonEventPayload": "",
                        "AlternativeLinkText": "",
                        "AlternativeLinkPayload": "",
                        "SecondAlternativeText": "",
                        "SecondAlternativeLinkPayload": "",
                    },
                    "IsShowNoClaimsPopup": False,
                    "TransactionTypeIdCurrentFilter": "",
                    "_transactionTypeIdCurrentFilterInDataFetchStatus": 1,
                    "StartDateTimeCurrentFilter": window.start_iso,
                    "_startDateTimeCurrentFilterInDataFetchStatus": 1,
                    "EndDateTimeCurrentFilter": window.end_iso,
                    "_endDateTimeCurrentFilterInDataFetchStatus": 1,
                    "ForceRefreshList": 0,
                    "_forceRefreshListInDataFetchStatus": 1,
                }
            },
        }
        result = self._post_json(TRANSACTIONS_ACTION_URL, payload, f"{BASE_URL}/Transactions")
        return result.get("data", {}).get("Transactions", {}).get("List", [])

    def fetch_totals(self, year: int, month: int, transaction_type: str = "All") -> dict[str, Any]:
        versions = self._ensure_versions()
        payload = {
            "versionInfo": {
                "moduleVersion": versions.module_version,
                "apiVersion": versions.totals_api_version,
            },
            "viewName": "MainFlow.Transactions",
            "screenData": {
                "variables": {
                    "TransactionTypeIdToWorkWith": transaction_type,
                    "InputParameterString": f"False{year}{month}",
                    "IsCollapsed": False,
                    "_isCollapsedInDataFetchStatus": 1,
                    "Month": month,
                    "_monthInDataFetchStatus": 1,
                    "Year": year,
                    "_yearInDataFetchStatus": 1,
                    "TransactionTypeIdSelected": "",
                    "_transactionTypeIdSelectedInDataFetchStatus": 1,
                }
            },
        }
        result = self._post_json(TOTALS_ACTION_URL, payload, f"{BASE_URL}/Transactions")
        return result.get("data", {})

    def fetch_month_data(self, year: int, month: int, max_records: int = DEFAULT_MAX_RECORDS) -> dict[str, Any]:
        transactions = enrich_transactions(self.fetch_transactions(year, month, max_records=max_records))
        totals = self.fetch_totals(year, month)
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": {
                "baseUrl": BASE_URL,
                "kind": "outsystems-json-api",
            },
            "summary": build_summary(year, month, transactions, totals),
            "transactions": transactions,
        }


def enrich_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = []
    for tx in transactions:
        prepared.append(
            {
                "id": tx.get("Id"),
                "date": tx.get("DateTransaction"),
                "typeId": tx.get("TransactionTypeId"),
                "type": tx.get("TransactionType"),
                "location": tx.get("LocationDescription"),
                "address": {
                    "street": tx.get("Street"),
                    "zipcode": tx.get("Zipcode"),
                    "city": tx.get("City"),
                    "countryCode": tx.get("LandCode"),
                },
                "licensePlate": tx.get("LicensePlate"),
                "cardNumber": tx.get("Cardnumber"),
                "product": tx.get("ProductDescription"),
                "amountEur": to_number(tx.get("AmoundCurrency")),
                "liters": to_number(tx.get("AmountProduct")),
                "mileage": to_number(tx.get("Mileage")),
                "note": tx.get("Note") or None,
            }
        )

    prepared.sort(key=lambda t: parse_iso(t["date"]))
    previous_fuel_mileage = None
    for tx in prepared:
        if tx["typeId"] != "FUEL":
            tx["distanceSincePreviousFuelKm"] = None
            tx["litersPer100Km"] = None
            continue

        mileage = tx["mileage"]
        liters = tx["liters"]
        if previous_fuel_mileage is not None and mileage is not None and liters is not None and mileage > previous_fuel_mileage:
            distance = mileage - previous_fuel_mileage
            tx["distanceSincePreviousFuelKm"] = round_value(distance, 0)
            tx["litersPer100Km"] = round_value((liters / distance) * 100, 2)
        else:
            tx["distanceSincePreviousFuelKm"] = None
            tx["litersPer100Km"] = None

        if mileage is not None:
            previous_fuel_mileage = mileage

    prepared.sort(key=lambda t: parse_iso(t["date"]), reverse=True)
    return prepared


def build_summary(year: int, month: int, transactions: list[dict[str, Any]], totals: dict[str, Any]) -> dict[str, Any]:
    fuel_transactions = [tx for tx in transactions if tx["typeId"] == "FUEL"]
    liters_per_100_values = [tx["litersPer100Km"] for tx in fuel_transactions if tx["litersPer100Km"] is not None]

    return {
        "year": year,
        "month": month,
        "transactionCount": len(transactions),
        "fuelTransactionCount": len(fuel_transactions),
        "totalAmountEur": round_value(sum(tx["amountEur"] or 0 for tx in transactions), 2),
        "fuelAmountEur": round_value(sum(tx["amountEur"] or 0 for tx in fuel_transactions), 2),
        "fuelLiters": round_value(sum(tx["liters"] or 0 for tx in fuel_transactions), 2),
        "averageLitersPer100Km": (
            round_value(sum(liters_per_100_values) / len(liters_per_100_values), 2)
            if liters_per_100_values
            else None
        ),
        "totalsFromPage": {
            "totalAmountEur": to_number(totals.get("TotalAmount")),
            "byType": [
                {
                    "typeId": item.get("TransactionTypeId"),
                    "amountEur": to_number(item.get("AmountSpent")),
                }
                for item in totals.get("TypeInformationList", {}).get("List", [])
            ],
        },
    }
