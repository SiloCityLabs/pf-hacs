# PF Check-In for Home Assistant

**By [SiloCityLabs](https://github.com/SiloCityLabs).** Unofficial Home Assistant integration that generates a Planet Fitness **digital keytag / check-in QR code** without the mobile app.

Setup uses the same Auth0 **email code** login as the official app. After setup, QR codes are computed **locally** (TOTP) — no continuous API polling.

> **Not affiliated with Planet Fitness.** This is an independent SiloCityLabs project. For personal use with your own membership. Gym door scanners and account policies can change without notice.

---

## Features

| Feature | Details |
|--------|---------|
| Config flow login | Enter membership email → integration waits for the emailed 6-digit code |
| Stored credentials | Email, Auth0 tokens, `accountId`, and `deviceId` saved on the config entry |
| Sensors | Email, Account ID, Device ID, QR payload, seconds remaining on the TOTP window |
| QR image | PNG `image` entity for Lovelace dashboards |
| Refresh button | Forces a local QR regenerate (does **not** call Planet Fitness APIs) |
| Local TOTP | Payload format `{AccountId}:{6-digit-TOTP}` matching the official app |

---

## How the QR works

The mobile app (new / “NewGen” users) builds:

```text
{AccountId}:{TOTP}
```

- **Secret** = UTF-8 bytes of `personalization.deviceId` (Base32 round-trip in the app is a no-op)
- **TOTP** = SHA-1, 30-second step, 6 digits (Otp.NET defaults)

After the one-time login during setup, Home Assistant only needs the stored `account_id` + `device_id`. Regenerating the QR never hits `api.planetfitness.com`.

---

## Requirements

- Home Assistant **2024.6.0** or newer
- A Planet Fitness membership that can sign in with **email code** (Auth0 passwordless)
- A registered `deviceId` on the account (open the official app once while logged in if setup reports “missing device”)

---

## Installation

### HACS (recommended)

1. Install [HACS](https://hacs.xyz/) if needed.
2. **HACS → Integrations → ⋮ → Custom repositories**
3. Add your repository URL (after you push this folder), category **Integration**.
4. Install **PF Check-In (SiloCityLabs)**.
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/planet_fitness_checkin` into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

Repository layout (same idea as Creality-Control):

```text
pf-hacs/
├── README.md
├── LICENSE
├── hacs.json
└── custom_components/
    └── planet_fitness_checkin/
        ├── __init__.py
        ├── manifest.json
        ├── const.py
        ├── auth.py
        ├── totp_qr.py
        ├── config_flow.py
        ├── coordinator.py
        ├── sensor.py
        ├── image.py
        ├── button.py
        ├── strings.json
        └── translations/en.json
```

---

## Configuration (setup wizard)

1. **Settings → Devices & services → Add integration**
2. Search for **PF Check-In**
3. Enter your membership **email**
4. Wait for the Auth0 email with a **6-digit code** (check spam)
5. Enter the code in the wizard (the UI waits on this step)
6. On success, the entry stores:
   - `email`
   - `account_id`
   - `device_id`
   - `access_token` / `refresh_token` (from Auth0; not required for day-to-day QR generation)

If the code is wrong or expired, the flow starts a **new** email challenge so you can try again.

---

## Entities created

| Entity type | Name | Purpose |
|-------------|------|---------|
| `sensor` | Email | Membership email |
| `sensor` | Account ID | `AccountId` used in the QR |
| `sensor` | Device ID | TOTP secret source |
| `sensor` | QR payload | Current `{AccountId}:{TOTP}` string |
| `sensor` | Code seconds remaining | Seconds left in the 30s TOTP window |
| `image` | Check-in QR | PNG suitable for dashboards |
| `button` | Refresh QR | Force regenerate payload + PNG locally |

Device name: **PF Check-In (`your@email`)** — manufacturer **SiloCityLabs** (not Planet Fitness).

---

## Dashboard example

Add the QR image and an optional refresh button. The image entity updates about every 15 seconds when the TOTP window changes; press **Refresh QR** right before scanning if you want an immediate redraw.

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## PF check-in
      Code refreshes every 30 seconds. Tap refresh before you scan if needed.
  - type: picture-entity
    entity: image.planet_fitness_your_email_check_in_qr
    camera_view: auto
    show_state: false
    show_name: false
  - type: entities
    entities:
      - sensor.planet_fitness_your_email_qr_payload
      - sensor.planet_fitness_your_email_code_seconds_remaining
      - button.planet_fitness_your_email_refresh_qr
```

> Entity IDs vary with your email / device name. Use the UI entity picker if unsure.

Alternative: **Picture entity** pointing at the `image.*_check_in_qr` entity, or a custom card that shows `sensor.*_qr_payload` as text.

### Refresh behavior (important)

| Action | Hits Planet Fitness API? |
|--------|---------------------------|
| Setup / re-auth (email + code) | **Yes** (Auth0 + `/user-details`) |
| Periodic coordinator tick (~15s) | **No** — local TOTP only |
| Press **Refresh QR** | **No** — local regenerate |

---

## Security notes

- Treat the config entry like a membership credential: `device_id` can mint valid door QR codes.
- Prefer HA secrets backups that are encrypted.
- Tokens are stored for possible future re-auth; QR generation does not need them after setup.
- This integration is for **your** account only.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| No email code | Spam folder; wait a minute; submit email again to resend |
| Invalid / expired code | Use the latest email; flow will request a new code after failure |
| Missing device id | Open the official PF app once, open the keytag screen, then re-run setup |
| QR not accepted at club | Confirm you’re a NewGen / non-legacy user; legacy barcodes differ |
| Image blank | Ensure `segno` installed (HA installs requirements from `manifest.json` on first load); check logs |

Enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.planet_fitness_checkin: debug
```

---

## Development

Logic mirrors the reverse-engineered official Android app (Auth0 `login.planetfitness.com`, `connection=email`, mobile API `https://api.planetfitness.com/mobile`).

Local smoke test of TOTP (outside HA):

```bash
python3 - <<'PY'
from custom_components.planet_fitness_checkin.totp_qr import qr_payload
print(qr_payload("YOUR_ACCOUNT_ID", "YOUR_DEVICE_ID"))
PY
```

---

## Disclaimer

Published by **SiloCityLabs**. Not affiliated with, endorsed by, or supported by Planet Fitness, Inc. Use at your own risk. Membership terms still apply. Door hardware and backend validation are controlled by Planet Fitness and may reject unofficial clients.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
