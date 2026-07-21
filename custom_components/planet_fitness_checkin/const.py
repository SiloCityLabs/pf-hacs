"""Constants for Planet Fitness Check-In."""

DOMAIN = "planet_fitness_checkin"

# Shown in HA device card as "By …" — must not imply Planet Fitness publishes this.
MANUFACTURER = "SiloCityLabs"
MODEL = "Unofficial check-in (not affiliated)"

CONF_EMAIL = "email"
CONF_ACCOUNT_ID = "account_id"
CONF_DEVICE_ID = "device_id"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"

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

# TOTP matches Otp.NET defaults used by the mobile app
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6

# Local TOTP refresh only — never hits Planet Fitness APIs after setup
UPDATE_INTERVAL_SECONDS = 15

ATTR_SECONDS_REMAINING = "seconds_remaining"
ATTR_PAYLOAD = "payload"
