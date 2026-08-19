# Reclamations Dashboard

Streamlit dashboard for submitting reclamations to a Google Sheet, plus a local
bridge (`sync.py`) that auto-fills each row's transaction details from a local
Postgres database.

## Local (with DB auto-fill)
- Install deps: `pip install -r requirements.txt`
- Run: `streamlit run streamlit_app.py`
- The app auto-starts `sync.py` (windowless, via `pythonw`) whenever the database
  is reachable on this machine (localhost). It polls the sheet and fills the
  transaction details from the DB based on `switch_ref` (or phone / montant /
  date). The bridge never runs on machines that can't reach the DB.
- For always-on, set up a Scheduled Task (on logon) that runs `pythonw sync.py`
  (see `run_sync.bat`).

## Streamlit Community Cloud
- The cloud app only writes to the shared Google Sheet. It cannot reach the local
  DB, so `sync.py` is never started there — **no console windows appear**.
- Set the `[gcp_service_account]` Streamlit secret with your service-account JSON.
- Keep your local `sync.py` running so that reclamations inserted from the cloud
  still get their DB-backed details filled into the shared sheet.
