# Contributing

## Local development

1. Copy `custom_components/movemove` into a Home Assistant test instance.
2. Restart Home Assistant.
3. Add the integration through the UI.
4. Check logs and diagnostics if setup fails.

## Before publishing

- verify config flow works in a real Home Assistant instance
- verify sensors update correctly
- verify `movemove.refresh` works
- verify diagnostics redact secrets correctly
- update `CHANGELOG.md`
- tag a release that matches `custom_components/movemove/manifest.json`
