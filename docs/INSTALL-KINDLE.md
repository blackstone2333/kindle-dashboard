# Kindle installation

This package is for a Kindle that already has a jailbreak and KOReader. It
does not install a jailbreak, modify KUAL, or change SSH settings.

## Install by USB

1. Exit KOReader before connecting the Kindle over USB.
2. Copy `koreader/plugins/kindleagentdashboard.koplugin` to the Kindle's
   `koreader/plugins/` directory.
3. Create the directory `koreader/settings/kindle-agent-dashboard/` if it does
   not exist.
4. Copy `config.example.json` there as `config.json` and replace both
   placeholders with the LAN Hub URL and the device token generated on your
   own computer.
5. Safely eject the Kindle and restart KOReader.
6. Open `Kindle Agent 看板` → `打开 V13 看板`.

The device must be on the same trusted home network as the Hub. The current
HTTP transport is intended for a private LAN only; do not expose it directly
to the public Internet.

## Offline behavior

The plugin keeps the last valid snapshot on the Kindle. If the Hub is
temporarily unavailable, the cached calendar, tasks, weather, and almanac stay
visible until a later sync succeeds.
