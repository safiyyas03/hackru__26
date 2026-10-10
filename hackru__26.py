"""
RU Grouped - find a group project partner at Rutgers on short notice.

Run with:  python -m streamlit run hackru__26.py

Persistence (created next to this script on first run):
  accounts.csv       -> username, password
  profiles_pool.csv  -> Name, Gender, Major, Attendance, Year, Contact, Bio
"""

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# --------------------------------------------------------------------------
st.set_page_config(page_title="RU Grouped", page_icon="🛡️", layout="centered")

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
ACCOUNTS_FILE = BASE_DIR / "accounts.csv"
PROFILES_FILE = BASE_DIR / "profiles_pool.csv"

ACCOUNT_COLS = ["username", "password"]
PROFILE_COLS = ["Name", "Gender", "Major", "Attendance", "Year", "Contact", "Bio"]

GENDERS = ["Any", "Female", "Male"]
MAJORS = ["All", "Computer Science", "Data Science", "Information Technology", "Other"]
YEARS = ["All", "Freshman", "Sophomore", "Junior", "Senior"]

# Courses shown on the course picker (taken from the prototype).
COURSES = [
    {"code": "CS213", "title": "Software Methodology", "prof": "Prof. Clifford", "section": "Section 01"},
    {"code": "CS111", "title": "Intro to Computer Science", "prof": "Prof. Rivera", "section": "Section 03"},
    {"code": "Topics in Science", "title": "Topics in Science", "prof": "Dr. Shinayaa", "section": "Section H1"},
]

SCARLET = "#CC0033"
SCARLET_DARK = "#A8002B"

SEED_PROFILES = [
    {
        "Name": "Alex Chen", "Gender": "Male", "Major": "Computer Science", "Attendance": 95,
        "Year": "Senior", "Contact": "ac1482@scarletmail.rutgers.edu",
        "Bio": "Backend nerd who likes clean Java. Can meet on weekday evenings at Hill Center.",
    },
    {
        "Name": "Jordan Smith", "Gender": "Female", "Major": "Data Science", "Attendance": 85,
        "Year": "Junior", "Contact": "js2290@scarletmail.rutgers.edu",
        "Bio": "Strong with Python and visualization. Happy to own the testing and docs.",
    },
    {
        "Name": "Manav Patel", "Gender": "Male", "Major": "Information Technology", "Attendance": 70,
        "Year": "Junior", "Contact": "mp3371@scarletmail.rutgers.edu",
        "Bio": "Full-stack dabbler, I can set up repos and CI quickly. Available on weekends.",
    },
    {
        "Name": "Priya Nair", "Gender": "Female", "Major": "Computer Science", "Attendance": 100,
        "Year": "Sophomore", "Contact": "pn0815@scarletmail.rutgers.edu",
        "Bio": "Never misses lecture. Looking for a reliable partner and a shared Google Doc.",
    },
    {
        "Name": "Sam Rodriguez", "Gender": "Male", "Major": "Other", "Attendance": 60,
        "Year": "Freshman", "Contact": "sr7742@scarletmail.rutgers.edu",
        "Bio": "Music and arts major taking CS as an elective. Great at slides and presenting.",
    },
]


# --------------------------------------------------------------------------
# File-system helpers (all defensive; users never see a traceback)
# --------------------------------------------------------------------------
def init_files() -> None:
    """Create the CSV files on first run. Seeds the profile pool."""
    try:
        if not ACCOUNTS_FILE.exists():
            pd.DataFrame(columns=ACCOUNT_COLS).to_csv(ACCOUNTS_FILE, index=False, encoding="utf-8")
    except Exception:
        pass
    try:
        if not PROFILES_FILE.exists():
            pd.DataFrame(SEED_PROFILES, columns=PROFILE_COLS).to_csv(
                PROFILES_FILE, index=False, encoding="utf-8"
            )
    except Exception:
        pass


def load_accounts() -> pd.DataFrame:
    try:
        df = pd.read_csv(ACCOUNTS_FILE, dtype=str, keep_default_na=False, encoding="utf-8")
        for col in ACCOUNT_COLS:
            if col not in df.columns:
                df[col] = ""
        return df[ACCOUNT_COLS]
    except Exception:
        return pd.DataFrame(columns=ACCOUNT_COLS)


def save_account(username: str, password: str) -> bool:
    try:
        accounts = load_accounts()
        new_row = pd.DataFrame([{"username": username, "password": password}])
        pd.concat([accounts, new_row], ignore_index=True).to_csv(
            ACCOUNTS_FILE, index=False, encoding="utf-8"
        )
        return True
    except Exception:
        return False


def load_profiles() -> pd.DataFrame:
    try:
        df = pd.read_csv(PROFILES_FILE, keep_default_na=False, encoding="utf-8")
    except Exception:
        df = pd.DataFrame(columns=PROFILE_COLS)
    for col in PROFILE_COLS:
        if col not in df.columns:
            df[col] = ""
    df = df[PROFILE_COLS].copy()
    df["Attendance"] = pd.to_numeric(df["Attendance"], errors="coerce").fillna(0).astype(int)
    return df


def save_profile(profile: dict) -> bool:
    try:
        pool = load_profiles()
        # Replace an existing card with the same name instead of duplicating it.
        pool = pool[pool["Name"].str.lower() != profile["Name"].lower()]
        pool = pd.concat([pool, pd.DataFrame([profile])], ignore_index=True)
        pool.to_csv(PROFILES_FILE, index=False, encoding="utf-8")
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------
def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800;900&display=swap');

        html, body, [class*="css"], .stApp {{
            font-family: 'Archivo', 'Segoe UI', Arial, sans-serif;
            color: #2B2B2B;
        }}
        .stApp {{ background: #FFFFFF; }}
        #MainMenu, footer {{ visibility: hidden; }}
        .block-container {{ max-width: 760px; padding-top: 2rem; }}

        h1, h2, h3 {{ color: #2B2B2B; font-weight: 900; letter-spacing: -0.01em; }}

        /* Brand line + wordmark */
        .brand-tag {{
            color: {SCARLET}; font-weight: 800; font-size: 0.8rem;
            text-align: center; margin-bottom: 0.25rem;
        }}
        .logo-r {{
            font-size: 7rem; line-height: 1; font-weight: 900; color: {SCARLET};
            text-align: center; -webkit-text-stroke: 3px #111; margin: 0;
        }}
        .wordmark {{
            font-size: 2.4rem; font-weight: 900; text-align: center; margin: 0;
        }}
        .tagline {{ text-align: center; font-weight: 700; margin-bottom: 1.5rem; }}
        .page-title {{ font-size: 2rem; font-weight: 900; text-align: center; margin: 0.5rem 0 0.2rem; }}
        .page-sub {{ text-align: center; color: #6B6B6B; font-weight: 600; margin-bottom: 1.25rem; }}

        /* Buttons: scarlet */
        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
            background: {SCARLET}; color: #FFFFFF; border: none; border-radius: 6px;
            font-weight: 800; padding: 0.6rem 1.2rem; width: 100%;
            box-shadow: 0 2px 6px rgba(0,0,0,0.18);
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            background: {SCARLET_DARK}; color: #FFFFFF; border: none;
        }}
        .stButton > button:focus-visible {{ outline: 3px solid #2B2B2B; outline-offset: 2px; }}
        .stButton > button p {{ font-weight: 800; }}

        /* Cards */
        .ru-card {{
            background: #FAF7F2; border: 2px solid #2B2B2B; border-radius: 10px;
            padding: 1rem 1.25rem; margin: 0.9rem 0 0.4rem; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }}
        .ru-card h3 {{ margin: 0 0 0.2rem; font-size: 1.25rem; }}
        .ru-card .meta {{ font-weight: 700; color: #2B2B2B; margin: 0.1rem 0; }}
        .ru-card .bio {{ color: #444; margin: 0.5rem 0; }}
        .ru-card a.mail {{
            display: inline-block; margin-top: 0.3rem; color: {SCARLET};
            font-weight: 800; text-decoration: none; border-bottom: 2px solid {SCARLET};
        }}
        .pill {{
            display: inline-block; background: {SCARLET}; color: #fff; font-weight: 800;
            font-size: 0.8rem; padding: 0.1rem 0.6rem; border-radius: 999px; margin-right: 0.4rem;
        }}
        .pill.gray {{ background: #2B2B2B; }}

        .profile-card {{
            background: #fff; border: 2px solid #2B2B2B; border-radius: 12px;
            padding: 1.5rem; text-align: center; margin: 1rem 0;
        }}
        .avatar {{
            width: 96px; height: 96px; border-radius: 50%; border: 3px solid {SCARLET};
            margin: 0 auto 0.6rem; display: flex; align-items: center; justify-content: center;
            font-size: 2.6rem; color: {SCARLET}; background: #FAF7F2;
        }}
        .profile-card h2 {{ margin: 0.2rem 0 0.8rem; }}
        .profile-card .line {{ font-weight: 800; font-size: 1.1rem; margin: 0.15rem 0; }}
        .profile-card .looking {{ color: {SCARLET}; font-weight: 900; font-size: 1.1rem; margin-top: 0.4rem; }}

        .sent-card {{
            background: #EDEDED; border-radius: 12px; padding: 2rem 1.25rem;
            text-align: center; margin: 1rem 0 1.5rem; box-shadow: 0 3px 8px rgba(0,0,0,0.12);
        }}
        .sent-card h2 {{ color: {SCARLET}; margin: 0 0 0.6rem; }}
        .sent-card .status {{ color: {SCARLET}; font-weight: 900; margin: 0.8rem 0; }}

        section[data-testid="stSidebar"] {{ background: #FAF7F2; border-right: 2px solid {SCARLET}; }}
        .stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 1rem; }}
        .stTabs [aria-selected="true"] {{ color: {SCARLET}; }}
        .stTabs [data-baseweb="tab-highlight"] {{ background-color: {SCARLET}; }}

        @media (max-width: 600px) {{
            .logo-r {{ font-size: 5rem; }}
            .wordmark {{ font-size: 1.8rem; }}
        }}
        @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Session state + navigation
# --------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "authenticated": False,
        "username": "",
        "page": "role",
        "role": None,
        "course": None,
        "selected_profile": None,
        "requests": [],
        "pending_toast": None,
        "history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go(page: str, remember: bool = True) -> None:
    """Navigate to a page, remembering where we came from for the back arrow."""
    if remember and st.session_state.page != page:
        st.session_state.history.append(st.session_state.page)
    st.session_state.page = page
    st.rerun()


def go_back() -> None:
    history = st.session_state.history
    st.session_state.page = history.pop() if history else "role"
    st.rerun()


def logout() -> None:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.page = "role"
    st.session_state.role = None
    st.session_state.course = None
    st.session_state.selected_profile = None
    st.session_state.history = []


def nav_bar() -> None:
    """Home / back controls, mirroring the icons at the bottom of each prototype screen."""
    left, _, right = st.columns([1, 4, 1])
    with left:
        if st.button("🏠 Home", key=f"home_{st.session_state.page}"):
            st.session_state.history = []
            go("role", remember=False)
    with right:
        if st.session_state.history and st.button("‹ Back", key=f"back_{st.session_state.page}"):
            go_back()


# --------------------------------------------------------------------------
# State 1: login / registration
# --------------------------------------------------------------------------
def render_login() -> None:
    st.markdown('<p class="logo-r">R</p>', unsafe_allow_html=True)
    st.markdown('<p class="wordmark">RU Grouped</p>', unsafe_allow_html=True)
    st.markdown('<p class="tagline">Find your project group</p>', unsafe_allow_html=True)

    _, center, _ = st.columns([1, 4, 1])
    with center:
        tab_in, tab_new = st.tabs(["Sign In", "Create Account"])

        with tab_in:
            with st.form("signin_form"):
                user = st.text_input("NetID / Username", key="si_user")
                pw = st.text_input("Password", type="password", key="si_pw")
                submitted = st.form_submit_button("Login")
            if submitted:
                user = user.strip()
                accounts = load_accounts()
                match = accounts[(accounts["username"] == user) & (accounts["password"] == pw)]
                if user and pw and not match.empty:
                    st.session_state.authenticated = True
                    st.session_state.username = user
                    st.session_state.pending_toast = f"Welcome back, {user}!"
                    st.rerun()
                else:
                    st.warning("That username and password don't match. Check them or create an account.")

        with tab_new:
            with st.form("signup_form"):
                new_user = st.text_input("Choose a username (your NetID works well)", key="su_user")
                new_pw = st.text_input("Choose a password", type="password", key="su_pw")
                created = st.form_submit_button("Create Account")
            if created:
                new_user = new_user.strip()
                if not new_user or not new_pw:
                    st.warning("Enter both a username and a password.")
                elif new_user.lower() in load_accounts()["username"].str.lower().tolist():
                    st.warning("That username is taken. Try another one or sign in.")
                elif save_account(new_user, new_pw):
                    st.session_state.authenticated = True
                    st.session_state.username = new_user
                    st.session_state.pending_toast = "Account created. You're signed in!"
                    st.rerun()
                else:
                    st.warning("We couldn't save your account right now. Please try again.")


# --------------------------------------------------------------------------
# Sidebar (greeting, logout, profile publisher)
# --------------------------------------------------------------------------
def render_sidebar() -> None:
    with st.sidebar:
        st.header(f"🛡️ Welcome, {st.session_state.username}!")
        if st.button("Log out", key="logout_btn"):
            logout()
            st.rerun()

        st.divider()
        st.subheader("Publish your profile")
        st.caption("Add your card to the pool so other students can find you.")
        with st.form("publish_form", clear_on_submit=True):
            name = st.text_input("Name", value=st.session_state.username)
            gender = st.selectbox("Gender", GENDERS[1:])
            major = st.selectbox("Major", MAJORS[1:])
            year = st.selectbox("Year", YEARS[1:])
            attendance = st.slider("Class attendance (%)", 0, 100, 80, step=5)
            contact = st.text_input("Scarletmail", placeholder="netid@scarletmail.rutgers.edu")
            bio = st.text_area("Short bio", max_chars=200, placeholder="Strengths, schedule, what you're looking for")
            publish = st.form_submit_button("Publish profile")
        if publish:
            if not name.strip() or not contact.strip():
                st.warning("Name and Scarletmail are required.")
            else:
                saved = save_profile(
                    {
                        "Name": name.strip(), "Gender": gender, "Major": major,
                        "Attendance": int(attendance), "Year": year,
                        "Contact": contact.strip(), "Bio": bio.strip(),
                    }
                )
                if saved:
                    st.toast("Your profile is live in the pool.", icon="✅")
                    st.success("Profile published.")
                else:
                    st.warning("We couldn't save your profile right now. Please try again.")


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def brand_tag() -> None:
    st.markdown('<div class="brand-tag">RU Grouped</div>', unsafe_allow_html=True)


def render_role() -> None:
    brand_tag()
    st.markdown('<div class="page-title">Who are you?</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Select your role to continue</div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 4, 1])
    with center:
        if st.button("Student", key="role_student"):
            st.session_state.role = "Student"
            go("courses")
        st.write("")
        if st.button("Instructor", key="role_instructor"):
            st.session_state.role = "Instructor"
            go("instructor")


def render_courses() -> None:
    brand_tag()
    st.markdown('<div class="page-title">Select Your Course</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Only courses with active group assignments are shown</div>',
        unsafe_allow_html=True,
    )
    for i, course in enumerate(COURSES):
        heading = (
            course["title"] if course["code"] == course["title"]
            else f'{course["code"]} - {course["title"]}'
        )
        st.markdown(
            f"""<div class="ru-card"><h3>{escape(heading)}</h3>
            <div class="meta">{escape(course['prof'])}</div>
            <div class="meta">{escape(course['section'])}</div></div>""",
            unsafe_allow_html=True,
        )
        if st.button("Find Partner", key=f"course_{i}"):
            st.session_state.course = heading
            go("matchmaker")
    st.write("")
    nav_bar()


def render_instructor() -> None:
    brand_tag()
    st.markdown('<div class="page-title">Instructor View</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">A snapshot of students looking for partners</div>', unsafe_allow_html=True)
    pool = load_profiles()
    c1, c2 = st.columns(2)
    c1.metric("Students in pool", len(pool))
    c2.metric("Avg. attendance", f"{int(pool['Attendance'].mean()) if len(pool) else 0}%")
    if len(pool):
        st.markdown("**Students by year**")
        st.bar_chart(pool["Year"].value_counts())
        st.dataframe(pool.drop(columns=["Contact"]), hide_index=True)
    else:
        st.info("No student profiles yet. Students can publish theirs from the sidebar.")
    nav_bar()


def filter_profiles(df: pd.DataFrame, gender: str, major: str, min_att: int, year: str) -> pd.DataFrame:
    """Sequential boolean-indexing sifter."""
    result = df
    if gender != "Any":
        result = result[result["Gender"] == gender]
    if major != "All":
        result = result[result["Major"] == major]
    result = result[result["Attendance"] >= min_att]
    if year != "All":
        result = result[result["Year"] == year]
    return result.sort_values("Attendance", ascending=False)


def render_matchmaker() -> None:
    brand_tag()
    st.markdown('<div class="page-title">🎯 Matchmaker Survey Options Selector</div>', unsafe_allow_html=True)
    course = st.session_state.course
    st.markdown(
        f'<div class="page-sub">{escape(course)}</div>' if course else '<div class="page-sub">Set your filters</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        c1, c2 = st.columns(2)
        gender = c1.selectbox("Gender", GENDERS, key="f_gender")
        major = c2.selectbox("Major", MAJORS, key="f_major")
        c3, c4 = st.columns(2)
        year = c3.selectbox("Year", YEARS, key="f_year")
        min_att = c4.slider("Minimum class attendance (%)", 0, 100, 0, step=5, key="f_att")

    pool = load_profiles()
    matches = filter_profiles(pool, gender, major, min_att, year)

    st.subheader("Available Partners")
    st.caption(f"{len(matches)} of {len(pool)} students match your survey")

    if matches.empty:
        st.info(
            "No students match these filters. Try lowering the attendance minimum, "
            "or set Gender, Major or Year to Any / All."
        )
    else:
        for idx, row in matches.iterrows():
            name = escape(str(row["Name"]))
            contact_raw = str(row["Contact"]).strip()
            contact = escape(contact_raw, quote=True)
            requested = row["Name"] in st.session_state.requests
            badge = '<span class="pill gray">Request pending</span>' if requested else ""
            st.markdown(
                f"""
                <div class="ru-card">
                    <h3>{name} {badge}</h3>
                    <div class="meta"><span class="pill">{escape(str(row['Year']))}</span>{escape(str(row['Major']))}</div>
                    <div class="meta">Attendance: {int(row['Attendance'])}%</div>
                    <div class="bio">{escape(str(row['Bio']))}</div>
                    <a class="mail" href="mailto:{contact}">✉ {contact}</a>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("View Profile", key=f"view_{idx}_{row['Name']}"):
                st.session_state.selected_profile = row.to_dict()
                go("profile")

    st.write("")
    if st.button("Back to courses", key="to_courses"):
        go("courses")


def render_profile() -> None:
    brand_tag()
    st.markdown('<div class="page-title">Student Profile</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Viewing profile</div>', unsafe_allow_html=True)
    p = st.session_state.selected_profile
    if not p:
        st.info("Pick a student from the results to see their profile.")
        if st.button("Back to results", key="no_profile_back"):
            go("matchmaker")
        return

    st.markdown(
        f"""
        <div class="profile-card">
            <div class="avatar">👤</div>
            <h2>{escape(str(p['Name']))}</h2>
            <div class="line">Major: {escape(str(p['Major']))}</div>
            <div class="line">Year: {escape(str(p['Year']))}</div>
            <div class="line">Attendance: {int(p['Attendance'])}%</div>
            <div class="looking">Looking for: Partner</div>
            <p style="margin-top:0.8rem;color:#444;">{escape(str(p['Bio']))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    already = p["Name"] in st.session_state.requests
    if already:
        st.info("You already sent a request to this student. Status: Pending.")
    elif st.button("Send Request", key="send_request"):
        st.session_state.requests.append(p["Name"])
        go("sent")
    st.write("")
    nav_bar()


def render_sent() -> None:
    brand_tag()
    st.markdown(
        """
        <div class="sent-card">
            <h2>Request Sent!</h2>
            <div>Your request has been sent.</div>
            <div class="status">Status: Pending</div>
            <div>Once accepted, you can find your partner's email through Canvas inbox.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Back to results", key="sent_back"):
        st.session_state.history = []
        go("matchmaker", remember=False)
    st.write("")
    nav_bar()


PAGES = {
    "role": render_role,
    "courses": render_courses,
    "instructor": render_instructor,
    "matchmaker": render_matchmaker,
    "profile": render_profile,
    "sent": render_sent,
}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    init_files()
    init_state()
    inject_css()

    if st.session_state.pending_toast:
        st.toast(st.session_state.pending_toast, icon="✅")
        st.session_state.pending_toast = None

    if not st.session_state.authenticated:
        render_login()
        return

    render_sidebar()
    PAGES.get(st.session_state.page, render_role)()


main()
