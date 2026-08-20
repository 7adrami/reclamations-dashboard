import os
import sys
import json
import hashlib
import hmac
import secrets
import datetime
import time
import socket
import subprocess

import streamlit as st
import pandas as pd
import gspread

import sync
import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHEET_FIELDS = [
    "switch_ref", "cut_off_id", "trans_date", "orig_inst", "orig_phone_number",
    "receiv_inst_id", "receiv_phone_number", "montant", "tx_type", "status", "decision",
]

TEXTS = {
    "fr": {
        "app_title": "Tableau de bord des Réclamations",
        "login_header": "Connexion",
        "username": "Nom d'utilisateur",
        "password": "Mot de passe",
        "login_btn": "Se connecter",
        "invalid": "identifiants invalides",
        "logout": "Déconnexion",
        "role": "Rôle",
        "user_mgmt": "Gestion des utilisateurs",
        "create_user": "Créer un utilisateur",
        "new_username": "Nouveau nom d'utilisateur",
        "new_password": "Nouveau mot de passe",
        "create_btn": "Créer l'utilisateur",
        "user_exists": "le nom d'utilisateur existe déjà",
        "user_created": "utilisateur créé",
        "chpw": "Changer le mot de passe",
        "chpw_username": "Nom d'utilisateur",
        "change_btn": "Changer le mot de passe",
        "unknown_user": "utilisateur inconnu",
        "pw_changed": "mot de passe changé",
        "insert_header": "Insérer une réclamation",
        "switch_ref": "switch_ref *",
        "cut_off_id": "cut_off_id",
        "trans_date": "trans_date (date & heure)",
        "orig_inst": "orig_inst",
        "orig_phone": "orig_phone_number",
        "receiv_inst": "receiv_inst_id",
        "receiv_phone": "receiv_phone_number",
        "montant": "montant",
        "tx_type": "tx_type",
        "status": "status",
        "decision": "décision",
        "add_btn": "Ajouter la réclamation",
        "required": "renseignez au moins un critère (switch_ref, téléphone, montant ou date)",
        "added": "Réclamation ajoutée",
        "results": "Résultats",
        "details": "Détails de la réclamation",
        "no_data": "Aucune donnée pour le moment",
        "sheet_error_title": ("Impossible d'accéder au Google Sheet (backend "
                              "d'authentification). Vérifiez les identifiants du "
                              "compte de service / les secrets Streamlit. Personne "
                              "ne peut se connecter tant que cela n'est pas corrigé."),
        "sheet_details": "Détails : ",
        "login_unavailable": ("La connexion est indisponible : le sheet est "
                              "inaccessible (voir l'erreur ci-dessus)."),
        "sheet_missing": ("Fichier d'identifiants introuvable. Sur Community Cloud, "
                          "cela signifie que le secret [gcp_service_account] est "
                          "manquant ou vide."),
        "sheet_denied": ("Le compte de service est authentifié mais l'accès au sheet "
                         "a été refusé. Partagez le classeur avec l'e-mail du compte "
                         "de service (donnez-lui le rôle Éditeur)."),
        "sheet_badkey": ("Google a rejeté le jeton d'authentification. Généralement "
                         "les sauts de ligne de private_key sont incorrects (doivent "
                         "être échappés en \\n) ou le secret est incomplet."),
        "sheet_401": ("Google a rejeté les identifiants (401). Le secret "
                      "[gcp_service_account] est probablement mal formé ou incomplet."),
    },
    "ar": {
        "app_title": "لوحة التحكم في الشكاوى",
        "login_header": "تسجيل الدخول",
        "username": "اسم المستخدم",
        "password": "كلمة المرور",
        "login_btn": "تسجيل الدخول",
        "invalid": "بيانات اعتماد غير صحيحة",
        "logout": "تسجيل الخروج",
        "role": "الدور",
        "user_mgmt": "إدارة المستخدمين",
        "create_user": "إنشاء مستخدم",
        "new_username": "اسم مستخدم جديد",
        "new_password": "كلمة مرور جديدة",
        "create_btn": "إنشاء المستخدم",
        "user_exists": "اسم المستخدم موجود بالفعل",
        "user_created": "تم إنشاء المستخدم",
        "chpw": "تغيير كلمة المرور",
        "chpw_username": "اسم المستخدم",
        "change_btn": "تغيير كلمة المرور",
        "unknown_user": "مستخدم غير معروف",
        "pw_changed": "تم تغيير كلمة المرور",
        "insert_header": "إدراج شكوى",
        "switch_ref": "switch_ref *",
        "cut_off_id": "cut_off_id",
        "trans_date": "trans_date (التاريخ والوقت)",
        "orig_inst": "orig_inst",
        "orig_phone": "orig_phone_number",
        "receiv_inst": "receiv_inst_id",
        "receiv_phone": "receiv_phone_number",
        "montant": "montant",
        "tx_type": "tx_type",
        "status": "status",
        "decision": "decision",
        "add_btn": "إضافة الشكوى",
        "required": "أدخل على الأقل معيارًا واحدًا (switch_ref أو هاتف أو مبلغ أو تاريخ)",
        "added": "تمت إضافة الشكوى",
        "results": "النتائج",
        "details": "تفاصيل الشكوى",
        "no_data": "لا توجد بيانات بعد",
        "sheet_error_title": ("تعذر الوصول إلى Google Sheet (الواجهة الخلفية "
                              "المصادقة). تحقق من بيانات اعتماد حساب الخدمة / أسرار "
                              "Streamlit. لا يمكن لأحد تسجيل الدخول حتى يتم إصلاح ذلك."),
        "sheet_details": "التفاصيل: ",
        "login_unavailable": "تسجيل الدخول غير متاح: لا يمكن الوصول إلى الجدول (انظر الخطأ أعلاه).",
        "sheet_missing": "ملف الاعتمادات غير موجود. على Community Cloud، هذا يعني أن السر [gcp_service_account] مفقود أو فارغ.",
        "sheet_denied": "تمت مصادقة حساب الخدمة ولكن تم رفض الوصول إلى الجدول. شارك جدول البيانات مع البريد الإلكتروني لحساب الخدمة (امنحه صلاحية محرر).",
        "sheet_badkey": "رفض Google رمز المصادقة. عادة ما تكون فواصل الأسطر في private_key غير صحيحة (يجب تهريبها كـ \\n) أو السر غير مكتمل.",
        "sheet_401": "رفض Google بيانات الاعتماد (401). السر [gcp_service_account] غالبًا غير صالح أو غير مكتمل.",
    },
}

COLUMN_LABELS = {
    "fr": {
        "switch_ref": "Réf. switch",
        "cut_off_id": "ID cut-off",
        "trans_date": "Date de transaction",
        "orig_inst": "Institution émettrice",
        "orig_phone_number": "Tél. émetteur",
        "receiv_inst_id": "Institution destinataire",
        "receiv_phone_number": "Tél. destinataire",
        "montant": "Montant",
        "tx_type": "Type de transaction",
        "status": "Statut",
        "decision": "Décision",
        "username": "Utilisateur",
        "inserted_at": "Date d'insertion",
    },
    "ar": {
        "switch_ref": "مرجع المحوّل",
        "cut_off_id": "معرف القطع",
        "trans_date": "تاريخ المعاملة",
        "orig_inst": "المؤسسة المرسلة",
        "orig_phone_number": "هاتف المرسل",
        "receiv_inst_id": "المؤسسة المستلمة",
        "receiv_phone_number": "هاتف المستلم",
        "montant": "المبلغ",
        "tx_type": "نوع المعاملة",
        "status": "الحالة",
        "decision": "القرار",
        "username": "المستخدم",
        "inserted_at": "تاريخ الإدراج",
    },
}


def t(key):
    return TEXTS[st.session_state.get("lang", "fr")].get(key, key)


def cl(col):
    return COLUMN_LABELS[st.session_state.get("lang", "fr")].get(col, col)


def load_users():
    """Load accounts from the 'users' worksheet (sheet-backed, deploy-safe)."""
    try:
        ws = sync.users_worksheet()
        rows = ws.get_all_values()
        if len(rows) < 2:
            return {}
        users = {}
        for r in rows[1:]:
            if len(r) >= 3 and r[0]:
                users[r[0]] = {
                    "password": r[1],
                    "role": r[2],
                    "created_at": r[3] if len(r) > 3 else "",
                }
        return users
    except Exception:
        return {}


def save_users(users):
    ws = sync.users_worksheet()
    rows = [["username", "password", "role", "created_at"]]
    for u, d in users.items():
        rows.append([
            u,
            d.get("password", ""),
            d.get("role", "user"),
            d.get("created_at", ""),
        ])
    ws.clear()
    ws.update(values=rows, range_name="A1", value_input_option="USER_ENTERED")


def hash_pw(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    d = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"{salt}:{d}"


def verify_pw(password, stored):
    if not stored or ":" not in stored:
        return False
    salt, want = stored.split(":", 1)
    got = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return hmac.compare_digest(got, want)


def _pid_alive(pid):
    """True if a Windows process with the given PID is still running."""
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def _db_reachable():
    """True if the Postgres port is reachable from this machine (i.e. we are
    running where the database lives, not on Streamlit Cloud)."""
    try:
        s = socket.create_connection((config.DB_HOST, int(config.DB_PORT)), timeout=1.5)
        s.close()
        return True
    except OSError:
        return False


_sync_log = None


def ensure_sync_running():
    """Start the sheet<->DB bridge (sync.py) when the database is reachable.

    Only starts when the database is reachable from this host (never on the
    cloud) and only if sync.py is not already running (checks its PID file).
    The database itself is never exposed anywhere. Safe to call on every
    rerun -- it spawns at most one bridge process.
    """
    global _sync_log
    if not _db_reachable():
        return
    pid_file = os.path.join(BASE_DIR, "sync.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return
        except (ValueError, OSError):
            pass
    log_path = os.path.join(BASE_DIR, "sync.log")
    try:
        # Open a fresh handle per spawn so the child owns its log file
        # independently of this process (avoids lost / buffered output).
        log_handle = open(log_path, "a", buffering=1)
    except OSError:
        log_handle = None
    DETACHED = 0x00000008
    NEW_GROUP = 0x00000200
    # Use pythonw (windowless) so no console pops up in the user's face.
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    try:
        subprocess.Popen(
            [pythonw, os.path.join(BASE_DIR, "sync.py")],
            cwd=BASE_DIR,
            stdout=log_handle,
            stderr=log_handle,
            creationflags=DETACHED | NEW_GROUP,
            close_fds=False,
        )
    except Exception:
        if log_handle:
            try:
                log_handle.write("[launcher] failed to start sync.py\n")
            except Exception:
                pass


def seed_users():
    try:
        users = load_users()
        if users:
            return
        users["elhadrami"] = {
            "password": hash_pw("limam2007"),
            "role": "admin",
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        save_users(users)
    except Exception:
        # Don't crash the app if the sheet is unreachable at startup.
        pass


def configure_from_secrets():
    """Make the app deployment-ready: pull the Google credentials from secrets."""
    try:
        s = st.secrets
        if "gcp_service_account" in s:
            data = dict(s["gcp_service_account"])
            tmp = os.path.join(BASE_DIR, ".streamlit_gsa.json")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            config.GOOGLE_CREDS_FILE = tmp
    except Exception:
        pass


def sheet_ok():
    """Return (ok, key) where key maps to a message in TEXTS."""
    try:
        sync.users_worksheet()
        return True, ""
    except FileNotFoundError:
        return False, "sheet_missing"
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        if "403" in msg or "permission" in low or "access" in low:
            return False, "sheet_denied"
        if "invalid_grant" in low or "jwt" in low or "token" in low:
            return False, "sheet_badkey"
        if "401" in msg or "unauthorized" in low or "refresh" in low:
            return False, "sheet_401"
        return False, "sheet_missing"


def bank_options():
    """Offer banks from the sheet data plus the static BANK_MAP (no DB needed)."""
    opts = []
    try:
        rows = read_reclamations()
        seen = set()
        for r in rows:
            for key in ("orig_inst", "receiv_inst_id"):
                c = str(r.get(key, "")).strip()
                if c and c not in seen:
                    seen.add(c)
                    opts.append((c, config.BANK_MAP.get(c, c)))
    except Exception:
        pass
    for c, n in config.BANK_MAP.items():
        if c not in [o[0] for o in opts]:
            opts.append((c, n))
    return opts


def append_reclamation(row, username):
    ws = sync.open_sheet_cached(60)
    hm = sync.read_header_map(ws)
    if not hm:
        # The first tab has no header row yet: create the canonical one so the
        # dashboard can both write and read reclamations from this sheet.
        cols = list(config.RESULT_COLUMNS) + ["username", "inserted_at"]
        ws.update(values=[cols], range_name="A1", value_input_option="USER_ENTERED")
        hm = {name: i + 1 for i, name in enumerate(cols)}
    row["username"] = username
    row["inserted_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    max_idx = max(hm.values())
    values = [""] * max_idx
    for name, idx in hm.items():
        values[idx - 1] = row.get(name, "")
    # Write to the first empty row in column A. We avoid ws.append_row because it
    # mis-aligns when the sheet has stray data far to the right (e.g. old rows in
    # columns 70+), pushing new rows out of the header's 1-13 column range.
    col_a = ws.col_values(1)
    next_row = len(col_a) + 1
    for i in range(1, len(col_a)):
        if col_a[i] == "":
            next_row = i + 1
            break
    ws.update(range_name=f"A{next_row}", values=[values],
              value_input_option="USER_ENTERED")


@st.cache_data(ttl=30)
def read_reclamations():
    for _ in range(5):
        try:
            ws = sync.open_sheet_cached(60)
            hm = sync.read_header_map(ws)
            allv = ws.get_all_values()
            rows = []
            for raw in allv[1:]:
                rows.append({name: (raw[i - 1] if i - 1 < len(raw) else "")
                             for name, i in hm.items()})
            return rows
        except gspread.exceptions.APIError as e:
            # Quota (429) errors are transient; back off and retry instead of
            # crashing the page on every rerun.
            time.sleep(8)
            sync.invalidate_open_cache()
    raise RuntimeError("Sheets API rate-limited; try again in a minute.")


st.set_page_config(
    page_title="Reclamations Dashboard",
    layout="wide",
)

if "lang" not in st.session_state:
    st.session_state.lang = "fr"
lang_choice = st.radio(
    "Langue / اللغة",
    options=["fr", "ar"],
    index=0,
    horizontal=True,
    format_func=lambda x: "Français" if x == "fr" else "العربية",
)
st.session_state.lang = lang_choice

configure_from_secrets()
sync.fix_clock_skew()
seed_users()
ensure_sync_running()

if "user" not in st.session_state:
    st.session_state.user = None

st.markdown(
    """<style>
    [data-testid="stAppViewContainer"] .main .block-container { padding-top: 2rem; }
    .stDataFrame { border-radius: 10px; }
    /* Phone-friendly adjustments */
    @media (max-width: 640px) {
      [data-testid="stAppViewContainer"] .main .block-container {
        padding: 0.75rem 0.5rem 2rem;
      }
      [data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        align-items: stretch !important;
      }
      [data-testid="stHorizontalBlock"] > div {
        width: 100% !important;
        min-width: 0 !important;
        margin: 0 0 0.5rem 0 !important;
      }
      /* 16px prevents iOS Safari auto-zoom when focusing inputs */
      input, select, textarea, .stTextInput > div input {
        font-size: 16px !important;
      }
      h1 { font-size: 1.6rem !important; }
      h2, h3 { font-size: 1.25rem !important; }
      .stDataFrame { overflow-x: auto; }
    }
    </style>""",
    unsafe_allow_html=True,
)

if st.session_state.lang == "ar":
    st.markdown(
        "<style>[data-testid=\"stAppViewContainer\"] { direction: rtl; }</style>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Login (conditional panel)
# ---------------------------------------------------------------------------
if st.session_state.user is None:
    st.title(t("app_title"))
    ok, key = sheet_ok()
    if not ok:
        st.error(t("sheet_error_title"))
        st.caption(t("sheet_details") + t(key))
    with st.container(border=True):
        st.subheader(t("login_header"))
        with st.form("login"):
            u = st.text_input(t("username"))
            p = st.text_input(t("password"), type="password")
            if st.form_submit_button(t("login_btn"), use_container_width=True):
                if not ok:
                    st.error(t("login_unavailable"))
                    st.stop()
                rec = load_users().get(u)
                if rec and verify_pw(p, rec["password"]):
                    st.session_state.user = {"username": u, "role": rec["role"]}
                    ensure_sync_running()
                    st.rerun()
                else:
                    st.error(t("invalid"))
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated area
# ---------------------------------------------------------------------------
user = st.session_state.user

with st.sidebar:
    st.title(t("app_title"))
    st.write(f"**{user['username']}**")
    st.caption(f"{t('role')}: {user['role']}")
    st.divider()
    if st.button(t("logout"), use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.title(t("app_title"))

if user["role"] == "admin":
    with st.expander(t("user_mgmt"), expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            with st.form("create"):
                st.markdown(f"**{t('create_user')}**")
                nu = st.text_input(t("new_username"))
                npw = st.text_input(t("new_password"), type="password")
                role = st.selectbox(t("role"), ["user", "admin"])
                if st.form_submit_button(t("create_btn"), use_container_width=True):
                    users = load_users()
                    if nu in users:
                        st.error(t("user_exists"))
                    elif nu and npw:
                        users[nu] = {
                            "password": hash_pw(npw),
                            "role": role,
                            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                        }
                        save_users(users)
                        st.success(t("user_created"))
        with c2:
            with st.form("chpw"):
                st.markdown(f"**{t('chpw')}**")
                cu = st.text_input(t("chpw_username"))
                cpw = st.text_input(t("new_password"), type="password")
                if st.form_submit_button(t("change_btn"), use_container_width=True):
                    users = load_users()
                    if cu in users:
                        users[cu]["password"] = hash_pw(cpw)
                        save_users(users)
                        st.success(t("pw_changed"))
                    else:
                        st.error(t("unknown_user"))

with st.container(border=True):
    st.subheader(t("insert_header"))
    with st.form("ins", clear_on_submit=True):
        switch_ref = st.text_input(t("switch_ref"))
        c1, c2 = st.columns(2)
        with c1:
            d = st.datetime_input(t("trans_date"), value=None)
            trans_date = d.strftime("%Y-%m-%d %H:%M:%S") if d else ""
            orig_phone = st.text_input(t("orig_phone"))
        with c2:
            montant = st.text_input(t("montant"))
            decision = st.text_input(t("decision"))
        if st.form_submit_button(t("add_btn"), use_container_width=True):
            if not (switch_ref.strip() or orig_phone.strip() or montant.strip() or d):
                st.error(t("required"))
            else:
                row = {
                    "switch_ref": switch_ref,
                    "orig_phone_number": orig_phone,
                    "montant": montant,
                    "trans_date": trans_date,
                    "decision": decision,
                }
                # The dashboard never touches the database. It only writes the
                # search criteria + the user's decision to the sheet; the local
                # sync.py polls the sheet, looks the row up in the database, and
                # fills the matched transaction details back into the sheet.
                try:
                    append_reclamation(row, user["username"])
                    read_reclamations.clear()
                    st.success(t("added"))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

st.subheader(t("results"))
rows = read_reclamations()
if rows:
    df = pd.DataFrame(rows)
    df.columns = [cl(c) for c in df.columns]
    st.dataframe(
        df,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tbl",
        height=420,
    )
    sel = st.session_state.get("tbl", {}).get("selection", {}).get("rows", [])
    if sel:
        r = df.iloc[sel[0]]
        with st.container(border=True):
            st.subheader(t("details"))
            d1, d2 = st.columns(2)
            for i, c in enumerate(df.columns):
                target = d1 if i % 2 == 0 else d2
                target.write(f"**{c}**: {r[c]}")
    else:
        st.info(t("no_data"))
