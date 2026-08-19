# ============================================================
# Gimtel Reclamations - Configuration
# ============================================================

# --- Database type: "postgresql" or "oracle" ---
DB_TYPE = "postgresql"  # <-- Change to "oracle" when switching to Oracle

# --- Connection parameters ---
DB_HOST = "localhost"
DB_PORT = 5433           # PostgreSQL default: 5432, Oracle default: 1521
DB_USER = "postgres"
DB_PASSWORD = "2007adrami"
DB_NAME = "gimtel"       # database to connect to (change if different)

# --- Google Sheet settings ---
# Path to the service-account JSON key (in this folder).
GOOGLE_CREDS_FILE = "credentials.json"
# Spreadsheet ID taken from the sheet URL.
SHEET_ID = "1DwlUi8aBzLQ5KkNQ6dpRM-UIP9edgXvyha71-QaAbdQ"
# None = use the first worksheet. Otherwise set the tab name, e.g. "Reclamations".
SHEET_NAME = None
# Worksheet that stores dashboard login accounts (sheet-backed, so they persist
# on deployed hosts where the local filesystem is ephemeral).
USERS_SHEET = "users"

# --- Sheet layout ---
# Row 1 = headers. You type lookup criteria into the SEARCH_COLUMNS below
# (any combination). The script fills the rest of that row from the database.
# 'decision' is sheet-only (you fill it); it is never written by the script.
HEADER_ROW = 1
FIRST_DATA_ROW = 2
MAX_DATA_ROWS = 1000

# Columns you may type to look up a transaction (when references are missing):
#   - switch_ref          : the transaction reference (exact)
#   - orig_phone_number   : sender's phone number
#   - montant             : amount
#   - trans_date          : date/time
SEARCH_COLUMNS = ["switch_ref", "orig_phone_number", "montant", "trans_date"]

# All columns written to the sheet. 'decision' is sheet-only.
RESULT_COLUMNS = [
    "switch_ref", "cut_off_id", "trans_date", "orig_inst",
    "orig_phone_number", "receiv_inst_id", "receiv_phone_number",
    "montant", "tx_type", "status", "decision",
]

# --- Polling ---
POLL_INTERVAL_SECONDS = 10

# Column that records who inserted the reclamation (sheet-only, written by the
# app/backend, never by this sync script). Rows that already have a username
# are treated as finalized reclamations and are left alone by the auto-fill.
USERNAME_COLUMN = "username"

# Friendly names for the institution codes shown in the app dropdowns.
# Only used to display a name next to a code; all codes found in the database
# are also offered (with the raw code as the name when unknown here).
BANK_MAP = {
    "00002": "CLICK",
    "00003": "MASRIVI",
    "00005": "CB",
    "00006": "AMANTY",
    "00009": "ORABANK",
    "00010": "BARID CASH",
    "00012": "BCIPAY",
    "00013": "ABM",
    "00015": "BIMBANK",
    "00018": "BANKILY",
    "00021": "BFI CASH",
    "00027": "SADAD",
    "08401": "BAMIS DIGITAL",
    "99001": "MOOV MONEY",
    "91201": "RASSIDY",
    "90201": "GAZA PAY",
    "92701": "MAUIRI PAY",
}
