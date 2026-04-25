# MoveMove Home Assistant Integration

Custom Home Assistant integration for MoveMove fuel card data.

## What this integration provides

- Config flow setup from Home Assistant UI.
- Periodic polling of your current month MoveMove summary and transactions.
- Sensors for totals, fuel amounts, liters, averages, and latest transaction details.

## Installation (HACS custom repository)

1. In HACS, add this repository as a **Custom repository** with category **Integration**.
2. Install **MoveMove** from HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration → MoveMove**.

## Notes

- Version is managed in `custom_components/movemove/manifest.json`.
- If login fails, provide your optional CSRF token during setup.
