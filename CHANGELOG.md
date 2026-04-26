# Changelog

## 0.1.7
- fixed login retry to rebuild versioned login payloads after auth resets, preventing false 403 "Invalid Login" failures

## 0.1.6
- fixed a 403 re-auth regression where CSRF state could be lost during retry, causing repeated authentication failures

## 0.1.5
- added adaptive refresh backoff with light jitter after repeated MoveMove failures to reduce hammering a degraded upstream
- added a diagnostic sensor for the age of the last fresh successful update
- added sensors for kilometers since last refuel, last refuel location, and last refuel liters per 100 km

## 0.1.4
- kept the last successful sensor payload available when MoveMove returns timeouts, 403s, or other transient API errors
- added persistent cache restore during startup so the integration can recover with stale data after reloads/restarts
- added a diagnostic "Refresh data" button entity on the MoveMove device
- exposed refresh/cache diagnostics in sensor attributes

## 0.1.3
- fixed blocking network I/O during Home Assistant setup by deferring API version discovery until executor-backed calls
- primed the login page before authentication to reduce expected CSRF bootstrap warnings

## 0.1.2
- fixed Home Assistant config flow loading by bundling the MoveMove API client inside the integration package
- added explicit `requests` dependency in the integration manifest

## 0.1.1
- improved CSRF bootstrap so manual seeding is often no longer required
- added device registration step to the stable auth flow
- added latest transaction sensors
- added diagnostics support
- added manual refresh service
- improved config flow and options validation

## 0.1.0
- initial HACS-ready MoveMove Home Assistant integration scaffold
- added MoveMove API client based on OutSystems JSON endpoints
- exposed monthly transaction and fuel summary sensors
