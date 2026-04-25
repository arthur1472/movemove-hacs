# MoveMove API client notes

## Files

- `scripts/movemove_api_client.py` — reusable Python client + CLI
- `scripts/test_movemove_api_client.py` — simple repeated-run verifier

## Required environment variables

- `MOVEMOVE_USERNAME`
- `MOVEMOVE_PASSWORD`

Optional bootstrap variable:
- `MOVEMOVE_CSRF_TOKEN`

The CSRF token is only used as an initial seed. After login, the client refreshes it from the `nr2Users` cookie and then performs the required device-registration step before fetching transaction data.

## CLI usage

```bash
MOVEMOVE_USERNAME='you@example.com' \
MOVEMOVE_PASSWORD='secret' \
MOVEMOVE_CSRF_TOKEN='initial-token-from-browser' \
python3 scripts/movemove_api_client.py --year 2026 --month 4 --out data/movemove-transactions-2026-04-api.json
```

## Verification

```bash
MOVEMOVE_USERNAME='you@example.com' \
MOVEMOVE_PASSWORD='secret' \
MOVEMOVE_CSRF_TOKEN='initial-token-from-browser' \
python3 scripts/test_movemove_api_client.py --year 2026 --month 4 --runs 5
```

## Output shape

Top-level keys:
- `generatedAt`
- `source`
- `summary`
- `transactions`

Useful Home Assistant-oriented summary fields:
- `summary.totalAmountEur`
- `summary.fuelAmountEur`
- `summary.fuelLiters`
- `summary.averageLitersPer100Km`
- `summary.transactionCount`
- `summary.fuelTransactionCount`

Useful transaction fields:
- `date`
- `typeId`
- `type`
- `location`
- `product`
- `amountEur`
- `liters`
- `mileage`
- `distanceSincePreviousFuelKm`
- `litersPer100Km`

## Notes for the next Home Assistant step

Good candidates for sensors:
- total amount this month
- fuel amount this month
- fuel liters this month
- average liters / 100 km
- latest transaction amount
- latest transaction location

The full transaction list can become coordinator data or sensor attributes.
