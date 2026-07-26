"""Constants for Planet Fitness Check-In."""

DOMAIN = "planet_fitness_checkin"

# HA device card "By …" — SiloCityLabs, not Planet Fitness.
MANUFACTURER = "SiloCityLabs"

CONF_EMAIL = "email"
CONF_ACCOUNT_ID = "account_id"
CONF_DEVICE_ID = "device_id"
CONF_ABC_BARCODE = "abc_barcode"
CONF_NEW_GEN_USER = "new_gen_user"
CONF_QR_FORMAT = "qr_format"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_PFX_MEMBERSHIP_ID = "pfx_membership_id"

# QR payload modes (mirrors official app KeytagService / DXKeytagViewModel)
QR_FORMAT_AUTO = "auto"
QR_FORMAT_NEWGEN = "newgen_totp"
QR_FORMAT_LEGACY_MOBILE = "legacy_mobile"
QR_FORMAT_LEGACY_PLAIN = "legacy_plain"

QR_FORMATS = [
    QR_FORMAT_AUTO,
    QR_FORMAT_NEWGEN,
    QR_FORMAT_LEGACY_MOBILE,
    QR_FORMAT_LEGACY_PLAIN,
]

# Auth0 / Planet Fitness (from official mobile app reverse engineering)
AUTH_BASE = "https://login.planetfitness.com"
API_BASE = "https://api.planetfitness.com/mobile"
CLIENT_ID = "V90DU2UBXm6sbkpk0rj08i0ol3rQey06"
AUDIENCE = "https://*.api.planetfitness.com"
SCOPE = "openid offline_access"
REDIRECT_URI = "com.planetfitness.pfmobileauth://callback"
APP_SCHEME = "com.planetfitness.pfmobileauth://"
# Auth0 Universal Login runs in a WebView/browser — match that (and our working pf_login.py).
# API calls use the app HttpClient UA ("pfx-mobile"), not the Auth0 page UA.
AUTH_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
API_USER_AGENT = "pfx-mobile"
# App LoginUniversal() also sends these on authorize
DEFAULT_COUNTRY_CODE = "US"
DEFAULT_UI_LOCALES = "en"

# TOTP matches Otp.NET defaults used by the mobile app (NewGen)
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6

# Legacy QRCodeSuffix.Mobile + CompactDateTime ("MMddyyyy-HHmmss") in UTC
LEGACY_CHANNEL_SUFFIX = "/mobile"
LEGACY_TIMESTAMP_FORMAT = "%m%d%Y-%H%M%S"

# Tick often enough for TOTP countdown / legacy QR; timestamp may lag a bit (app does too)
UPDATE_INTERVAL_SECONDS = 30

# Black Card guests: re-render QR on the same 30s tick, but only hit the guest
# list endpoint every few minutes.
GUEST_TICK_SECONDS = 30
GUEST_POLL_SECONDS = 300

# Check-in history (My Journey): poll less often; window matches the app's year view.
CHECKIN_POLL_SECONDS = 3600
CHECKIN_HISTORY_DAYS = 365
CHECKIN_ATTR_LIMIT = 50

ATTR_SECONDS_REMAINING = "seconds_remaining"
ATTR_PAYLOAD = "payload"
ATTR_QR_FORMAT = "qr_format"
ATTR_RESOLVED_FORMAT = "resolved_format"
ATTR_GUEST_COUNT = "guest_count"
ATTR_GUESTS = "guests"
ATTR_UNLOCKED_COUNT = "unlocked_count"
ATTR_BARCODE = "barcode"
ATTR_USER_ID = "user_id"
ATTR_CHECKINS = "checkins"
ATTR_LAST_CLUB = "last_club"
ATTR_WINDOW_DAYS = "window_days"
