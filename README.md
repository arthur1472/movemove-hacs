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

## HACS version + description behavior

HACS does **not** read the integration version from `manifest.json` for the repository card/update entity.  
For HACS to show a semantic version (for example `v0.1.3`) instead of a commit SHA, publish a **GitHub Release** for each version.

- `manifest.json` version is used by Home Assistant.
- HACS repository/update version is based on GitHub releases.
- If no release exists, HACS falls back to a commit hash.

Repository description in HACS comes from the **GitHub repository description** (set in the repo “About” section), not from `hacs.json`.

## Troubleshooting and logs

If configuration fails with `Failed to connect to MoveMove`, detailed errors are logged under:

- `custom_components.movemove.config_flow` (during setup validation)
- `custom_components.movemove.coordinator` (during periodic refresh)
- `custom_components.movemove.movemove_client` (debug endpoint attempts)

### Where to see logs in Home Assistant

1. Go to **Settings → System → Logs**.
2. Filter for `movemove` or `custom_components.movemove`.
3. To get endpoint-level debug details, add this to `configuration.yaml` and restart Home Assistant:

```yaml
logger:
  default: info
  logs:
    custom_components.movemove: debug
```
