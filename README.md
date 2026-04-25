# MoveMove Home Assistant integration

HACS-ready Home Assistant custom integration for MoveMove / OnTheMove.

## Features

- monthly summary sensors
- latest transaction sensors
- automatic OutSystems JSON API polling
- diagnostics support with redaction
- manual `movemove.refresh` service
- config flow + options flow

## Sensors

- latest transaction amount
- latest transaction liters
- total amount
- fuel amount
- fuel liters
- average liters per 100 km
- transaction count
- fuel transaction count

The transaction-count sensor exposes the full current-period transaction list as attributes.
Latest-transaction sensors expose extra context like date, type, location, and product.

## Setup

1. Put this repository on GitHub.
2. Add it to HACS as a custom repository, or publish it publicly for normal HACS installation.
3. Install the integration.
4. Restart Home Assistant.
5. Add the MoveMove integration from the Home Assistant UI.
6. Enter:
   - username
   - password
   - optional initial CSRF token
   - max records
   - scan interval

## Bootstrap / CSRF

The integration now tries to self-bootstrap the CSRF flow automatically.
In many cases you can leave the CSRF field empty.
If first-time login still fails, provide an initial CSRF token once and retry.

## Manual refresh

Service name:
- `movemove.refresh`

## Repository structure

- `custom_components/movemove/` — Home Assistant integration
- `scripts/movemove_api_client.py` — underlying Python API client
- `scripts/test_movemove_api_client.py` — repeated-run verifier
- `CHANGELOG.md` — release notes

## Current publication status

This repo is close to HACS/GitHub publication-ready, but you should still do one real-world validation in a Home Assistant instance before publishing a release.

Recommended final checks:
- install in a real HA test environment
- run through config flow
- verify sensor creation
- verify `movemove.refresh`
- verify diagnostics output

## License

MIT
