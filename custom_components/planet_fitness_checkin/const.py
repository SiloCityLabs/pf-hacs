"""Constants for Planet Fitness Check-In."""

DOMAIN = "planet_fitness_checkin"

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
USER_AGENT = "pfx-mobile"

# TOTP matches Otp.NET defaults used by the mobile app
TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6

# Local TOTP refresh only — never hits Planet Fitness APIs after setup
UPDATE_INTERVAL_SECONDS = 15

ATTR_SECONDS_REMAINING = "seconds_remaining"
ATTR_PAYLOAD = "payload"
