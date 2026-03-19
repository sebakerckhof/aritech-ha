"""Constants for the Aritech integration."""

DOMAIN = "aritech_ats"

# Configuration keys
CONF_ENCRYPTION_KEY = "encryption_key"
CONF_PIN_CODE = "pin_code"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PANEL_TYPE = "panel_type"

# Panel types
PANEL_TYPE_X500 = "x500"
PANEL_TYPE_X700 = "x700"

# Defaults
DEFAULT_PORT = 32000

# Device info
MANUFACTURER = "Aritech (KGS)"
MODEL_PREFIX = "ATS"

# Connection timeouts (seconds)
CONNECT_TIMEOUT = 30
INITIALIZE_TIMEOUT = 60
