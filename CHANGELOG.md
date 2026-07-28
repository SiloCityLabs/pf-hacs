# Changelog

All notable changes to **Planet Fitness Check-In** (`pf-hacs`) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project versions with [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.6] - 2026-07-28

### Fixed

- Companion `Custom element doesn't exist: pf-checkin-card` after HA upgrades: mirror the card into `/local/planet_fitness_checkin/` (config/www) and register that Lovelace resource, matching how HACS frontend cards load

## [2.1.5] - 2026-07-28

### Fixed

- Last check-in / history timestamps: PF My Journey returns local wall-clock times with a misleading `Z` suffix; interpret them in the Home Assistant timezone so weekday ~8 PM / Sunday ~5 PM visits display correctly

## [2.1.4] - 2026-07-26

### Fixed

- Club access switch no longer errors with HTTP 400 when Planet Fitness rejects lock/unlock for Unified Club Pass **pilot** guests (`CannotLockAndUnlockPilotGuest`); treated as a no-op because there is no alternate disable API

## [2.1.3] - 2026-07-26

### Fixed

- Companion / WebView card load: serve card JS with `charset=utf-8`, `Cache-Control: no-cache`, and ASCII-only source

### Changed

- Card editor uses Home Assistant `getConfigForm` entity picker (filtered to Planet Fitness check-in QR images) instead of a plain text field
- Stub config prefers the primary `me@…` check-in QR entity when present

## [2.1.2] - 2026-07-26

### Fixed

- `Custom element doesn't exist: pf-checkin-card` on Companion / cold start by registering a Lovelace resource (in addition to `add_extra_js_url`)

## [2.1.1] - 2026-07-26

### Fixed

- Check-in card unlock chip staying on “Locked” after unlocking a guest and going back
- Card icon rendering as a white blob; switched to yellow thumbs-up on purple

## [2.1.0] - 2026-07-26

### Added

- Lovelace card `custom:pf-checkin-card`: PF logo button → person picker → auto-unlock guest → show QR
- Websocket helper to list member + guests for a check-in image entity
- Static frontend assets under `/planet_fitness_checkin_static/`

## [2.0.0] - 2026-07-26

### Added

- Black Card guests: per-guest device, club access switch, guest QR image, payload sensor
- Check-in history sensors (count / last check-in) via `/view/checkins`
- Guest list polling and unlock/lock API (`/black-card/guest`)

## [1.1.2] - 2026-07-25

### Changed

- Member check-in QR refresh interval: every **30 seconds** instead of every second

## [1.1.1] - 2026-07-25

### Fixed

- Legacy `AbcBarcode` lookup path (`memberships[0].abcBarcode`)

## [1.1.0] - 2026-07-25

### Added

- Legacy QR formats: `{AbcBarcode}/mobile/{MMddyyyy-HHmmss}` (UTC) and plain barcode
- Options flow to override QR format (NewGen / legacy mobile / legacy plain)

### Changed

- Local brand icons; device manufacturer shown as **SiloCityLabs** (not Planet Fitness)
- HACS packaging cleanup (removed invalid `filename` field); README screenshot

## [1.0.3] - 2026-07-21

### Fixed

- Relative Auth0 `/authorize/resume` redirects during email-code login

## [1.0.2] - 2026-07-21

### Fixed

- Auth0 browser `User-Agent` matched to the working local login flow

## [1.0.1] - 2026-07-21

### Fixed

- Auth0 email-code redirect capture during Home Assistant config flow setup

## [1.0.0] - 2026-07-21

### Added

- Initial Home Assistant / HACS integration for Planet Fitness digital keytag QR (NewGen TOTP)
- Config flow login via Planet Fitness Auth0 email code
- Local QR image entity (no continuous Planet Fitness API traffic for the member keytag)

[2.1.6]: https://github.com/SiloCityLabs/pf-hacs/commit/6e5a9af
[2.1.5]: https://github.com/SiloCityLabs/pf-hacs/commit/9283059
[2.1.4]: https://github.com/SiloCityLabs/pf-hacs/commit/2cc11d6
[2.1.3]: https://github.com/SiloCityLabs/pf-hacs/commit/05d7f18
[2.1.2]: https://github.com/SiloCityLabs/pf-hacs/commit/71b5e88
[2.1.1]: https://github.com/SiloCityLabs/pf-hacs/commit/61e5b46
[2.1.0]: https://github.com/SiloCityLabs/pf-hacs/commit/8e55c9d
[2.0.0]: https://github.com/SiloCityLabs/pf-hacs/commit/7f6b8cb
[1.1.2]: https://github.com/SiloCityLabs/pf-hacs/commit/a68e9a0
[1.1.1]: https://github.com/SiloCityLabs/pf-hacs/commit/5dd5f8b
[1.1.0]: https://github.com/SiloCityLabs/pf-hacs/commit/ee89670
[1.0.3]: https://github.com/SiloCityLabs/pf-hacs/releases/tag/v1.0.3
[1.0.2]: https://github.com/SiloCityLabs/pf-hacs/commit/9a154bc
[1.0.1]: https://github.com/SiloCityLabs/pf-hacs/commit/bd59b41
[1.0.0]: https://github.com/SiloCityLabs/pf-hacs/commit/2e35241
