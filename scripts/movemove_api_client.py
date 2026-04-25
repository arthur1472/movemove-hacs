#!/usr/bin/env python3
"""MoveMove API client using the app's underlying OutSystems JSON endpoints.

This module avoids browser automation for the real data fetch path so it can be
reused later in a Home Assistant custom integration.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

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
    csrf_token: Optional[str] = None
    keep_me_logged_in: bool = True


def round_value(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)



def to_number(value: Any) -> Optional[float]:
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
        session: Optional[requests.Session] = None,
    ):
        self.credentials = credentials
        self.timeout = timeout
        self.session = session or requests.Session()
        self._last_csrf_token: Optional[str] = credentials.csrf_token
        self.versions = self._discover_versions()

    @classmethod
    def from_env(cls, timeout: int = DEFAULT_TIMEOUT) -> "MoveMoveClient":
        username = os.getenv("MOVEMOVE_USERNAME")
        password = os.getenv("MOVEMOVE_PASSWORD")
        csrf_token = os.getenv("MOVEMOVE_CSRF_TOKEN")
        if not username or not password:
            raise MoveMoveError("Missing MOVEMOVE_USERNAME or MOVEMOVE_PASSWORD")
        return cls(
            MoveMoveCredentials(
                username=username,
                password=password,
                csrf_token=csrf_token,
            ),
            timeout=timeout,
        )

    def _discover_versions(self) -> ApiVersions:
        moduleinfo = self.session.get(MODULEINFO_URL, timeout=self.timeout)
        moduleinfo.raise_for_status()
        manifest = moduleinfo.json()["manifest"]
        module_version = manifest["versionToken"]
        url_versions = manifest["urlVersions"]

        def extract_api_version(path: str, marker: str) -> str:
            manifest_path = f"/OnTheMove{path}"
            script_url = f"{BASE_URL}{path}{url_versions[manifest_path]}"
            js = self.session.get(script_url, timeout=self.timeout)
            js.raise_for_status()
            text = js.text
            start = text.find(marker)
            if start == -1:
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

    def _csrf_token(self) -> str:
        nr2 = self.session.cookies.get("nr2Users")
        if nr2 and "crf%3d" in nr2:
            part = nr2.split("crf%3d", 1)[1].split("%3b", 1)[0]
            token = urllib.parse.unquote(part).rstrip(";")
            self._last_csrf_token = token
            return token
        if self._last_csrf_token:
            return self._last_csrf_token
        raise MoveMoveError("No CSRF token found in session cookies")

    def _base_headers(self, referer: str) -> Dict[str, str]:
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

    def _refresh_csrf_from_cookies(self) -> None:
        self._last_csrf_token = self._csrf_token()

    def _post_json(self, url: str, payload: Dict[str, Any], referer: str) -> Dict[str, Any]:
        response = self.session.post(
            url,
            headers=self._base_headers(referer),
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code == 403 and url != LOGIN_ACTION_URL:
            self.login()
            response = self.session.post(
                url,
                headers=self._base_headers(referer),
                json=payload,
                timeout=self.timeout,
            )

        response.raise_for_status()
        data = response.json()
        if data.get("exception"):
            raise MoveMoveError(data["exception"].get("message") or str(data["exception"]))
        self._refresh_csrf_from_cookies()
        return data

    def login(self) -> Dict[str, Any]:
        payload = {
            "versionInfo": {
                "moduleVersion": self.versions.module_version,
                "apiVersion": self.versions.login_api_version,
            },
            "viewName": "Common.Login",
            "inputParameters": {
                "Username": self.credentials.username,
                "Password": self.credentials.password,
                "KeepMeLoggedIn": self.credentials.keep_me_logged_in,
            },
        }

        headers = self._base_headers(LOGIN_PAGE_URL)
        token = self._last_csrf_token
        if token:
            headers["x-csrftoken"] = token
        response = self.session.post(
            LOGIN_ACTION_URL,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        if response.status_code == 403:
            self._refresh_csrf_from_cookies()
            response = self.session.post(
                LOGIN_ACTION_URL,
                headers={**self._base_headers(LOGIN_PAGE_URL), "x-csrftoken": self._csrf_token()},
                json=payload,
                timeout=self.timeout,
            )

        response.raise_for_status()
        data = response.json()
        if data.get("exception"):
            raise MoveMoveError(data["exception"].get("message") or str(data["exception"]))
        if not data.get("data", {}).get("Result"):
            raise MoveMoveError("Login failed")

        self._refresh_csrf_from_cookies()
        self.register_device_login()
        return data["data"]

    def register_device_login(self, is_movemove: bool = False) -> None:
        payload = {
            "versionInfo": {
                "moduleVersion": self.versions.module_version,
                "apiVersion": self.versions.device_login_api_version,
            },
            "viewName": "Common.Login",
            "inputParameters": {
                "DeviceInfo": DEFAULT_DEVICE_INFO,
                "IsMoveMove": is_movemove,
            },
        }
        self._post_json(DEVICE_LOGIN_ACTION_URL, payload, LOGIN_PAGE_URL)

    def fetch_transactions(self, year: int, month: int, max_records: int = DEFAULT_MAX_RECORDS) -> List[Dict[str, Any]]:
        window = month_window(year, month)
        payload = {
            "versionInfo": {
                "moduleVersion": self.versions.module_version,
                "apiVersion": self.versions.transactions_api_version,
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

    def fetch_totals(self, year: int, month: int, transaction_type: str = "All") -> Dict[str, Any]:
        payload = {
            "versionInfo": {
                "moduleVersion": self.versions.module_version,
                "apiVersion": self.versions.totals_api_version,
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

    def fetch_month_data(self, year: int, month: int, max_records: int = DEFAULT_MAX_RECORDS) -> Dict[str, Any]:
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



def enrich_transactions(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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



def build_summary(year: int, month: int, transactions: List[Dict[str, Any]], totals: Dict[str, Any]) -> Dict[str, Any]:
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



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch MoveMove transactions without Playwright")
    parser.add_argument("--username", default=os.getenv("MOVEMOVE_USERNAME"))
    parser.add_argument("--password", default=os.getenv("MOVEMOVE_PASSWORD"))
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--csrf-token", default=os.getenv("MOVEMOVE_CSRF_TOKEN"))
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    if not args.username or not args.password:
        raise SystemExit("Missing MOVEMOVE_USERNAME or MOVEMOVE_PASSWORD")

    client = MoveMoveClient(
        MoveMoveCredentials(
            username=args.username,
            password=args.password,
            csrf_token=args.csrf_token,
        )
    )
    client.login()
    output = client.fetch_month_data(args.year, args.month, max_records=args.max_records)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
        return

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
