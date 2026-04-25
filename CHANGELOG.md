# Changelog

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
