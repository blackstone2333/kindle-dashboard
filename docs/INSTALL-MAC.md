# Mac Hub installation

This is the current reference source adapter: macOS EventKit supplies
Calendar and Reminders data, while the Hub supplies weather and calendar
metadata to the Kindle.

## Requirements

- macOS with Calendar and Reminders permissions;
- Python 3.9 or newer;
- the Mac and Kindle on the same trusted LAN.

## First run

```sh
python3 -m pip install --target .runtime/vendor -r requirements-live.txt
python3 connectors/macos/export_snapshot.py --output .runtime/hub/apple.json
python3 tools/live_hub.py start
python3 tools/live_hub.py status
```

Allow Calendar and Reminders access when macOS asks. The Hub creates a private
device token in `.runtime/hub/device-token`; copy it into the Kindle's local
`config.json`, but never commit or publish it.

The default port is `18501`. Keep it on the home LAN and configure the weather
location in `.runtime/hub/weather-location.json`.

The current reference service is a normal background process. A launchd
autostart helper is planned but is not required for development use.
