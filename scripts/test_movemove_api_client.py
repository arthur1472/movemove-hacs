#!/usr/bin/env python3
"""Small verification script for the MoveMove API client.

Usage:
  MOVEMOVE_USERNAME=... MOVEMOVE_PASSWORD=... MOVEMOVE_CSRF_TOKEN=... \
  python3 scripts/test_movemove_api_client.py --year 2026 --month 4 --runs 3
"""

from __future__ import annotations

import argparse
import json

from movemove_api_client import MoveMoveClient



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify repeated MoveMove API fetches")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=100)
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    for run in range(1, args.runs + 1):
        client = MoveMoveClient.from_env()
        client.login()
        payload = client.fetch_month_data(args.year, args.month, max_records=args.max_records)
        print(
            json.dumps(
                {
                    "run": run,
                    "transactionCount": payload["summary"]["transactionCount"],
                    "fuelTransactionCount": payload["summary"]["fuelTransactionCount"],
                    "totalAmountEur": payload["summary"]["totalAmountEur"],
                    "averageLitersPer100Km": payload["summary"]["averageLitersPer100Km"],
                }
            )
        )


if __name__ == "__main__":
    main()
