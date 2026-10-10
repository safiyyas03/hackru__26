"""
RU Grouped - find a group project partner at Rutgers on short notice.

Run with:  python -m streamlit run hackru__26.py      (needs streamlit >= 1.40)

Screens / flow (matches the prototype):
  Login -> Who are you? -> Select Your Course -> Filters -> Available Partners
        -> Student Profile -> Send Request -> Request Sent! -> Back to results

CSV BACKEND (NetID is the key column everywhere)
------------------------------------------------
Put your CSV files next to this script (or in a ./data or ./csv folder).
Files are recognised by their COLUMN HEADERS, not their file names:

  Students  : NetID, Password, Last_Name, First_Name, Gender, Grad_Year, Major
  Class     : NetID, Attendance           one file per class, e.g. class_CS213.csv
              (or one file with NetID, Course, Attendance)
              Attendance can be 0-100, 0-1, "85%", or Often / Sometimes / Rarely
  Courses   : Course, Title, Professor, Section          (optional)
  Profiles  : NetID, Bio                                 (optional, created on demand)
  Requests  : From_NetID, To_NetID, Course, Status, Timestamp   (created on demand)

If no Students file is found, demo files are created so the app runs out of the box.
Demo login:  kl5521 / pass1234
"""

import re
from datetime import date, datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="RU Grouped", page_icon="🛡️", layout="centered", initial_sidebar_state="collapsed"
)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SEARCH_DIRS = [BASE_DIR, BASE_DIR / "data", BASE_DIR / "csv"]

STUDENT_COLS = ["NetID", "Password", "Last_Name", "First_Name", "Gender", "Grad_Year", "Major"]
COURSE_COLS = ["Course", "Title", "Professor", "Section"]
PROFILE_COLS = ["NetID", "Bio"]
REQUEST_COLS = ["From_NetID", "To_NetID", "Course", "Status", "Timestamp"]

# Header aliases -> canonical column names (matching ignores case, spaces, _ and -)
ALIASES = {
    "netid": "NetID", "username": "NetID", "user": "NetID",
    "password": "Password", "pass": "Password",
    "lastname": "Last_Name", "last": "Last_Name", "surname": "Last_Name",
    "firstname": "First_Name", "first": "First_Name", "givenname": "First_Name",
    "gender": "Gender", "sex": "Gender",
    "gradyear": "Grad_Year", "graduationyear": "Grad_Year", "gradyr": "Grad_Year",
    "major": "Major",
    "attendance": "Attendance", "attendancepct": "Attendance", "attendancepercent": "Attendance",
    "attendancehabit": "Attendance", "attendancerate": "Attendance",
    "bio": "Bio",
    "course": "Course", "coursecode": "Course", "class": "Course", "classcode": "Course",
    "title": "Title", "coursetitle": "Title", "classname": "Title",
    "professor": "Professor", "prof": "Professor", "instructor": "Professor",
    "section": "Section",
    "fromnetid": "From_NetID", "tonetid": "To_NetID", "status": "Status", "timestamp": "Timestamp",
}

YEAR_OF = {"1st": "Freshman", "2nd": "Sophomore", "3rd": "Junior", "4th": "Senior"}
YEAR_LABEL = {"Freshman": "1st Year", "Sophomore": "2nd Year", "Junior": "3rd Year", "Senior": "4th Year"}
HABIT_WORDS = {"always": 95, "often": 90, "sometimes": 65, "rarely": 30, "never": 10}

BTN = "#B5243B"
BTN_DARK = "#8F1B2E"
SCARLET = "#CC0033"

AVATAR_SVG = (
    '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<circle cx="50" cy="50" r="47" fill="#fff" stroke="currentColor" stroke-width="3"/>'
    '<circle cx="50" cy="39" r="15" fill="none" stroke="currentColor" stroke-width="3"/>'
    '<path d="M22 84c3-17 15-26 28-26s25 9 28 26" fill="none" stroke="currentColor" stroke-width="3"/>'
    "</svg>"
)
PERSON_ICON = (
    '<svg viewBox="0 0 64 64" width="46" height="46" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    f'<circle cx="32" cy="18" r="11" fill="none" stroke="{SCARLET}" stroke-width="5"/>'
    f'<path d="M10 54c0-12 9-19 22-19s22 7 22 19z" fill="none" stroke="{SCARLET}" stroke-width="5" '
    'stroke-linejoin="round"/></svg>'
)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def code_key(s) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(s).upper()).strip("_")


def academic_end_year() -> int:
    today = date.today()
    return today.year + 1 if today.month >= 8 else today.year


def standing(grad_year) -> str:
    try:
        diff = int(float(grad_year)) - academic_end_year()
    except (TypeError, ValueError):
        return "Unknown"
    if diff <= 0:
        return "Senior"
    return {1: "Junior", 2: "Sophomore"}.get(diff, "Freshman")


def parse_attendance(series: pd.Series) -> pd.Series:
    """Accept 85, '85%', 0.85 or Often/Sometimes/Rarely and return 0-100."""
    def one(v):
        s = str(v).strip().lower().replace("%", "")
        if s in HABIT_WORDS:
            return float(HABIT_WORDS[s])
        try:
            return float(s)
        except ValueError:
            return 0.0
    nums = series.map(one).astype(float)
    if len(nums) and nums.max() <= 1:
        nums = nums * 100
    return nums.round().astype(int)


def habit(pct: int) -> str:
    return "Often" if pct >= 80 else ("Sometimes" if pct >= 50 else "Rarely")


def major_group(major: str) -> str:
    s = str(major).lower()
    if "politic" in s:
        return "Other"
    if any(k in s for k in ("business", "account", "financ", "market", "econom", "management", "supply")):
        return "Business"
    if any(k in s for k in ("computer", "data", "information", "math", "stat", "engineer", "physic",
                            "chem", "bio", "cyber", "artificial", "science", "stem", "tech")):
        return "STEM"
    if any(k in s for k in ("music", "art", "design", "theat", "dance", "film", "media", "drama")):
        return "Music / Arts"
    return "Other"


def ensure_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df


def short_name(first: str, last: str) -> str:
    last = str(last).strip()
    return f"{first} {last[0]}." if last else str(first)


# --------------------------------------------------------------------------
# CSV backend (every call is defensive; users never see a traceback)
# --------------------------------------------------------------------------
def read_raw(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [ALIASES.get(norm(c), str(c).strip()) for c in raw.columns]
    return raw.loc[:, ~raw.columns.duplicated()]


def seed_demo_files() -> None:
    """Create demo CSVs only when no Students file exists anywhere."""
    try:
        for d in SEARCH_DIRS:
            if d.is_dir():
                for p in d.glob("*.csv"):
                    try:
                        cols = set(read_raw(p).columns)
                    except Exception:
                        continue
                    if "NetID" in cols and ("Password" in cols or "First_Name" in cols):
                        return
        students = [
            ["ac1482", "pass1234", "Chen", "Alex", "Male", 2027, "Computer Science"],
            ["js2290", "pass1234", "Smith", "Jordan", "Female", 2028, "Data Science"],
            ["mp3371", "pass1234", "Patel", "Manav", "Male", 2028, "Information Technology"],
            ["pn0815", "pass1234", "Nair", "Priya", "Female", 2029, "Computer Science"],
            ["sr7742", "pass1234", "Rodriguez", "Sam", "Male", 2030, "Music Performance"],
            ["kl5521", "pass1234", "Lee", "Karen", "Female", 2027, "Computer Science"],
            ["db4410", "pass1234", "Brooks", "Dana", "Female", 2029, "Business Analytics"],
        ]
        pd.DataFrame(students, columns=STUDENT_COLS).to_csv(BASE_DIR / "students.csv", index=False)
        pd.DataFrame(
            [["CS213", "Software Methodology", "Prof. Clifford", "Section 01"],
             ["Topics in Science", "", "Dr. Shinayaa", "Section H1"]],
            columns=COURSE_COLS,
        ).to_csv(BASE_DIR / "courses.csv", index=False)
        pd.DataFrame(
            [["ac1482", "Backend nerd who likes clean Java. Free weekday evenings."],
             ["js2290", "Strong with Python and visualization. Happy to own testing and docs."],
             ["pn0815", "Never misses lecture. Wants a reliable partner and a shared doc."],
             ["db4410", "Business analytics major looking to learn more about software."]],
            columns=PROFILE_COLS,
        ).to_csv(BASE_DIR / "profiles.csv", index=False)
        pd.DataFrame(
            [["ac1482", 35], ["js2290", 40], ["mp3371", 30], ["pn0815", 95], ["kl5521", 70], ["db4410", 85]],
            columns=["NetID", "Attendance"],
        ).to_csv(BASE_DIR / "class_CS213.csv", index=False)
        pd.DataFrame(
            [["kl5521", 80], ["sr7742", 55], ["db4410", 90], ["js2290", 45]],
            columns=["NetID", "Attendance"],
        ).to_csv(BASE_DIR / "class_TOPICS_IN_SCIENCE.csv", index=False)
    except Exception:
        pass


def load_data() -> dict:
    data = {
        "Students": pd.DataFrame(columns=STUDENT_COLS),
        "Courses": pd.DataFrame(columns=COURSE_COLS),
        "Profiles": pd.DataFrame(columns=PROFILE_COLS),
        "Requests": pd.DataFrame(columns=REQUEST_COLS),
        "classes": {},   # code -> DataFrame(NetID, Attendance)
        "src": {},       # table/code -> (path, is_long_format, original_course_value)
    }
    files = []
    for d in SEARCH_DIRS:
        if d.is_dir():
            files += sorted(d.glob("*.csv"))
    for path in files:
        try:
            raw = read_raw(path)
        except Exception:
            continue
        cols = set(raw.columns)
        try:
            if "NetID" in cols and ("Password" in cols or "First_Name" in cols):
                data["Students"] = raw
                data["src"]["Students"] = (path, False, "")
            elif "From_NetID" in cols and "To_NetID" in cols:
                data["Requests"] = raw
                data["src"]["Requests"] = (path, False, "")
            elif "NetID" in cols and "Attendance" in cols:
                if "Course" in cols:
                    for course_val, grp in raw.groupby("Course"):
                        code = code_key(course_val)
                        data["classes"][code] = grp.drop(columns=["Course"]).reset_index(drop=True)
                        data["src"][code] = (path, True, course_val)
                else:
                    stem = code_key(path.stem)
                    stem = re.sub(r"^(CLASS|ATTENDANCE)_|_ATTENDANCE$", "", stem)
                    data["classes"][stem] = raw
                    data["src"][stem] = (path, False, "")
            elif "NetID" in cols and "Bio" in cols:
                data["Profiles"] = raw
                data["src"]["Profiles"] = (path, False, "")
            elif "Course" in cols and cols & {"Title", "Professor", "Section"}:
                data["Courses"] = raw
                data["src"]["Courses"] = (path, False, "")
        except Exception:
            continue

    data["Students"] = ensure_cols(data["Students"], STUDENT_COLS)
    data["Profiles"] = ensure_cols(data["Profiles"], PROFILE_COLS)
    data["Courses"] = ensure_cols(data["Courses"], COURSE_COLS)
    data["Requests"] = ensure_cols(data["Requests"], REQUEST_COLS)
    for key in ("Students", "Profiles"):
        data[key]["NetID"] = data[key]["NetID"].astype(str).str.strip().str.lower()
    for key in ("From_NetID", "To_NetID"):
        data["Requests"][key] = data["Requests"][key].astype(str).str.strip().str.lower()
    for code, df in list(data["classes"].items()):
        df = ensure_cols(df, ["NetID", "Attendance"])
        df["NetID"] = df["NetID"].astype(str).str.strip().str.lower()
        data["classes"][code] = df
    return data


def save_csv(df: pd.DataFrame, path: Path) -> bool:
    try:
        df.to_csv(path, index=False, encoding="utf-8")
        return True
    except Exception:
        return False


def table_path(data: dict, name: str, default: str) -> Path:
    return data["src"][name][0] if name in data["src"] else BASE_DIR / default


def find_student(data: dict, netid: str):
    hit = data["Students"][data["Students"]["NetID"] == str(netid).strip().lower()]
    return hit.iloc[0] if not hit.empty else None


def register_student(data: dict, row: dict) -> bool:
    df = pd.concat([data["Students"], pd.DataFrame([row])], ignore_index=True)
    return save_csv(df, table_path(data, "Students", "students.csv"))


def save_bio(data: dict, netid: str, bio: str) -> bool:
    prof = data["Profiles"]
    prof = prof[prof["NetID"] != netid]
    prof = pd.concat([prof, pd.DataFrame([{"NetID": netid, "Bio": bio}])], ignore_index=True)
    return save_csv(prof, table_path(data, "Profiles", "profiles.csv"))


def enroll(data: dict, netid: str, code: str, attendance: int = 100) -> bool:
    try:
        path, is_long, course_val = data["src"][code]
        df = read_raw(path)
        row = {"NetID": netid, "Attendance": str(attendance)}
        if is_long:
            row["Course"] = course_val
        if (df["NetID"].astype(str).str.lower() == netid).any() if "NetID" in df.columns else False:
            if not is_long or ((df["NetID"].astype(str).str.lower() == netid) & (df["Course"] == course_val)).any():
                return True
        return save_csv(pd.concat([df, pd.DataFrame([row])], ignore_index=True), path)
    except Exception:
        return False


def add_request(data: dict, me: str, other: str, code: str) -> bool:
    row = {"From_NetID": me, "To_NetID": other, "Course": code, "Status": "Pending",
           "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
    df = pd.concat([data["Requests"], pd.DataFrame([row])], ignore_index=True)
    return save_csv(df[REQUEST_COLS], table_path(data, "Requests", "requests.csv"))


def has_request(data: dict, me: str, other: str, code: str) -> bool:
    r = data["Requests"]
    return bool(((r["From_NetID"] == me) & (r["To_NetID"] == other) & (r["Course"] == code)).any())


def enrolled_courses(data: dict, netid: str) -> dict:
    out = {}
    for code, df in data["classes"].items():
        mine = df[df["NetID"] == netid]
        if not mine.empty:
            out[code] = int(parse_attendance(mine["Attendance"]).iloc[0])
    return out


def course_info(data: dict, code: str) -> dict:
    c = data["Courses"]
    hit = c[c["Course"].map(code_key) == code]
    if hit.empty:
        return {"Course": code.replace("_", " "), "Title": "", "Professor": "", "Section": ""}
    return hit.iloc[0].to_dict()


def course_label(data: dict, code: str) -> str:
    info = course_info(data, code)
    return f"{info['Course']} - {info['Title']}" if str(info.get("Title", "")).strip() else str(info["Course"])


def course_pool(data: dict, code: str, me: str) -> pd.DataFrame:
    """Join class attendance + Students + Profiles on NetID."""
    cols = ["NetID", "Name", "Short", "Gender", "Major", "Group", "Year", "Attendance", "Habit", "Bio"]
    cls = data["classes"].get(code)
    if cls is None or cls.empty:
        return pd.DataFrame(columns=cols)
    cls = cls[["NetID", "Attendance"]].copy()
    cls["Attendance"] = parse_attendance(cls["Attendance"])
    cls = cls.drop_duplicates("NetID")
    stu = data["Students"].drop(columns=["Password"]).drop_duplicates("NetID")
    prof = data["Profiles"][["NetID", "Bio"]].drop_duplicates("NetID")
    m = cls.merge(stu, on="NetID", how="inner").merge(prof, on="NetID", how="left")
    m = m[m["NetID"] != me].copy()
    if m.empty:
        return pd.DataFrame(columns=cols)
    m["Bio"] = m["Bio"].fillna("")
    m["Name"] = (m["First_Name"].astype(str) + " " + m["Last_Name"].astype(str)).str.strip()
    m["Short"] = [short_name(f, l) for f, l in zip(m["First_Name"], m["Last_Name"])]
    m["Year"] = m["Grad_Year"].map(standing)
    m["Group"] = m["Major"].map(major_group)
    m["Habit"] = m["Attendance"].map(habit)
    return m[cols].reset_index(drop=True)


def filter_pool(pool: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Sequential boolean-indexing sifter. An empty selection means 'no filter'."""
    r = pool
    genders = [g for g in f["gender"] if g != "Any"]
    if "Any" not in f["gender"] and genders:
        r = r[r["Gender"].isin(genders)]
    if f["year"]:
        r = r[r["Year"].isin([YEAR_OF[y] for y in f["year"]])]
    if f["major"]:
        r = r[r["Group"].isin(f["major"])]
    if f["habit"]:
        r = r[r["Habit"].isin(f["habit"])]
    return r.sort_values("Attendance", ascending=False)


# --------------------------------------------------------------------------
# Styling (phone-frame look from the prototype)
# --------------------------------------------------------------------------
def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;800;900&family=Alfa+Slab+One&display=swap');

        html, body, [class*="css"], .stApp, button, input, textarea {{
            font-family: 'Unbounded', 'Archivo Black', 'Arial Black', Arial, sans-serif !important;
        }}
        .stApp {{ background: #1b1b1b; }}
        header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {{ display: none !important; }}

        /* ---- the phone ---- */
        .block-container, [data-testid="stMainBlockContainer"] {{
            max-width: 430px !important; margin: 1.2rem auto !important;
            background: #fff; color: #111; position: relative; min-height: 800px;
            border: 9px solid #0a0a0a; border-radius: 46px; box-shadow: 0 0 0 3px #bdbdbd;
            padding: 3.2rem 1.5rem 1.2rem !important;
        }}
        .block-container::before, [data-testid="stMainBlockContainer"]::before {{
            content: ""; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
            width: 150px; height: 28px; background: #0a0a0a; border-radius: 0 0 20px 20px;
        }}
        @media (max-width: 480px) {{
            .stApp {{ background: #fff; }}
            .block-container, [data-testid="stMainBlockContainer"] {{
                border: none; border-radius: 0; box-shadow: none; margin: 0 auto !important; min-height: 100vh;
            }}
            .block-container::before, [data-testid="stMainBlockContainer"]::before {{ display: none; }}
        }}

        /* ---- typography ---- */
        .brand {{ color: {SCARLET}; font-weight: 800; font-size: 0.55rem; text-align: center; margin-bottom: 1.4rem; }}
        .screen-title {{ font-weight: 900; font-size: 1.35rem; text-align: center; line-height: 1.15; margin: 0.4rem 0 0.2rem; }}
        .screen-sub {{ color: #777; font-weight: 800; font-size: 0.55rem; text-align: center; margin-bottom: 1.2rem; line-height: 1.5; }}
        .logo-r {{ font-family: 'Alfa Slab One', 'Rockwell', Georgia, serif !important; font-size: 8.5rem; line-height: 1;
                   color: {SCARLET}; -webkit-text-stroke: 5px #0a0a0a; paint-order: stroke fill; text-align: center; margin: 0.5rem 0 0; }}
        .wordmark {{ font-weight: 900; font-size: 1.9rem; text-align: center; margin: 0; text-shadow: 2px 3px 3px rgba(0,0,0,0.35); }}
        .tagline {{ font-weight: 800; font-size: 0.6rem; text-align: center; margin: 0 0 1.4rem; text-shadow: 1px 2px 2px rgba(0,0,0,0.3); }}
        .who {{ font-weight: 900; font-size: 1.45rem; text-align: center; text-shadow: 2px 3px 3px rgba(0,0,0,0.3); }}
        .who b {{ color: {SCARLET}; }}
        .f-head {{ font-weight: 900; font-size: 0.8rem; text-align: center; margin: 1rem 0 0.3rem; text-shadow: 1px 2px 2px rgba(0,0,0,0.25); }}
        .muted {{ color: #777; font-size: 0.55rem; font-weight: 700; text-align: center; }}

        /* ---- inputs ---- */
        .stTextInput label p, .stTextArea label p, .stSelectbox label p {{ font-weight: 900; font-size: 0.7rem; }}
        .stTextInput input, .stTextArea textarea {{
            background: #d9d9d9 !important; border: none !important; border-radius: 8px;
            box-shadow: inset 0 3px 5px rgba(0,0,0,0.25); color: #111;
        }}
        [data-baseweb="select"] > div {{ background: #d9d9d9 !important; border: none !important; border-radius: 8px; }}
        div[data-testid="stForm"] {{ border: none; padding: 0; }}

        /* ---- buttons (scarlet by default) ---- */
        .stButton > button, .stFormSubmitButton > button {{
            background: {BTN}; color: #fff; border: none; border-radius: 6px; width: 100%;
            font-weight: 800; font-size: 0.7rem; padding: 0.75rem 0.8rem;
            box-shadow: 0 3px 6px rgba(0,0,0,0.3); letter-spacing: 0.02em;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{ background: {BTN_DARK}; color: #fff; border: none; }}
        .stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible {{ outline: 3px solid #111; outline-offset: 2px; }}
        .stButton > button p {{ font-weight: 800; }}
        .st-key-role_student button, .st-key-role_instructor button {{ padding: 1.9rem 1rem; font-size: 0.95rem; border-radius: 4px; }}
        .st-key-send_request button, .st-key-sent_back button, .st-key-profile_back button, .st-key-apply_filters button {{ padding: 1rem; }}
        .st-key-send_request button {{ font-size: 0.8rem; }}

        /* gray buttons: View Profile (except first) + back to courses */
        [class*="st-key-pcard_"] button {{ background: #e6e6e6; color: #222; box-shadow: none; font-size: 0.6rem; padding: 0.55rem; }}
        [class*="st-key-pcard_"] button:hover {{ background: #d0d0d0; color: #111; }}
        .st-key-pcard_0 button {{ background: {BTN}; color: #fff; }}
        .st-key-pcard_0 button:hover {{ background: {BTN_DARK}; color: #fff; }}
        .st-key-back_courses button, .st-key-logout button {{ background: #e6e6e6; color: #222; font-size: 0.6rem; padding: 0.55rem 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.25); }}
        .st-key-back_courses button:hover, .st-key-logout button:hover {{ background: #d0d0d0; color: #111; }}

        /* ---- course + partner cards ---- */
        [class*="st-key-course_"] {{ border: 2px solid #111; border-radius: 8px; padding: 0.7rem; margin-bottom: 0.9rem; box-shadow: 0 2px 4px rgba(0,0,0,0.25); }}
        [class*="st-key-course_"] button {{ padding: 0.55rem; font-size: 0.6rem; }}
        .course-t {{ font-weight: 900; font-size: 0.62rem; line-height: 1.55; margin-bottom: 0.5rem; }}
        [class*="st-key-pcard_"] {{ border: 2px solid #111; border-radius: 8px; padding: 0.6rem; margin-bottom: 0.9rem; box-shadow: 0 2px 4px rgba(0,0,0,0.25); }}
        .pc {{ display: flex; gap: 0.8rem; align-items: center; margin-bottom: 0.5rem; }}
        .pc .av {{ width: 52px; height: 52px; flex: none; color: #777; }}
        .pc .t {{ font-weight: 900; font-size: 0.62rem; line-height: 1.55; }}

        /* ---- profile + sent ---- */
        .profile-card {{ border: 2px solid #111; border-radius: 8px; padding: 1.4rem 0.8rem; text-align: center; margin: 0.4rem 0 1.6rem; box-shadow: 0 2px 4px rgba(0,0,0,0.25); }}
        .profile-card .av {{ width: 92px; height: 92px; margin: 0 auto 0.6rem; color: {SCARLET}; }}
        .profile-card .nm {{ font-weight: 900; font-size: 1.15rem; margin-bottom: 0.8rem; }}
        .profile-card .ln {{ font-weight: 900; font-size: 0.8rem; line-height: 1.7; }}
        .profile-card .looking {{ color: {SCARLET}; font-weight: 900; font-size: 0.8rem; }}
        .profile-card .bio {{ color: #555; font-size: 0.55rem; font-weight: 600; margin-top: 0.8rem; line-height: 1.6; }}
        .sent-card {{ background: #ececec; border-radius: 10px; padding: 1.8rem 1rem; text-align: center; margin: 0.4rem 0 1.6rem; box-shadow: 0 3px 8px rgba(0,0,0,0.25); }}
        .sent-card .h {{ color: {SCARLET}; font-weight: 900; font-size: 1.05rem; margin-bottom: 0.8rem; }}
        .sent-card .p {{ font-weight: 800; font-size: 0.62rem; line-height: 1.6; }}
        .sent-card .status {{ color: {SCARLET}; font-weight: 900; font-size: 0.62rem; margin: 0.8rem 0 1.6rem; }}

        /* ---- filter checkboxes + major tiles ---- */
        .stCheckbox label p {{ font-weight: 900; font-size: 0.6rem; }}
        .st-key-major_tiles [data-testid="stCheckbox"] {{
            border: 2px solid #111; border-radius: 8px; padding: 1.3rem 0.4rem 0.4rem; min-height: 64px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.25); justify-content: center;
        }}
        .st-key-major_tiles [data-testid="stCheckbox"] label {{ justify-content: center; }}

        /* ---- bottom nav (home + back icons) ---- */
        .st-key-navbar button {{ background: transparent; color: #111; box-shadow: none; padding: 0.3rem; width: auto; }}
        .st-key-navbar button:hover {{ background: #eee; color: #111; }}
        .st-key-navbar button p {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }}
        .st-key-navbar [data-testid="stHorizontalBlock"] {{ align-items: center; }}
        .st-key-navbar [data-testid="stColumn"]:last-child {{ display: flex; justify-content: flex-end; }}

        .stTabs [data-baseweb="tab-highlight"] {{ background-color: {SCARLET}; }}
        [data-testid="stExpander"] {{ border: none; }}
        [data-testid="stExpander"] summary p {{ font-size: 0.55rem; font-weight: 800; color: #555; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Session state + navigation
# --------------------------------------------------------------------------
EMPTY_FILTERS = {"gender": [], "year": [], "major": [], "habit": []}


def init_state() -> None:
    defaults = {
        "authenticated": False,
        "username": "",
        "page": "login",
        "role": None,
        "course": None,
        "selected": None,
        "filters": {k: list(v) for k, v in EMPTY_FILTERS.items()},
        "history": [],
        "pending_toast": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def go(page: str, remember: bool = True) -> None:
    if remember and st.session_state.page != page:
        st.session_state.history.append(st.session_state.page)
    st.session_state.page = page
    st.rerun()


def go_back() -> None:
    h = st.session_state.history
    st.session_state.page = h.pop() if h else "role"
    st.rerun()


def logout() -> None:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.page = "login"
    st.session_state.role = None
    st.session_state.course = None
    st.session_state.selected = None
    st.session_state.history = []
    st.session_state.filters = {k: list(v) for k, v in EMPTY_FILTERS.items()}


def nav_bar() -> None:
    st.write("")
    with st.container(key="navbar"):
        left, right = st.columns(2)
        with left:
            if st.button("Home", icon=":material/home:", key=f"nav_home_{st.session_state.page}"):
                st.session_state.history = []
                go("role", remember=False)
        with right:
            if st.session_state.history and st.button(
                "Back", icon=":material/chevron_left:", key=f"nav_back_{st.session_state.page}"
            ):
                go_back()


def brand() -> None:
    st.markdown('<div class="brand">RU Grouped</div>', unsafe_allow_html=True)


def title(text: str, sub: str = "") -> None:
    st.markdown(f'<div class="screen-title">{escape(text)}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="screen-sub">{escape(sub)}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------
def screen_login(data: dict) -> None:
    st.markdown('<p class="logo-r">R</p>', unsafe_allow_html=True)
    st.markdown('<p class="wordmark">RU Grouped</p>', unsafe_allow_html=True)
    st.markdown('<p class="tagline">Find your project group</p>', unsafe_allow_html=True)

    with st.form("login_form", border=False):
        netid = st.text_input("NetID", key="li_netid")
        pw = st.text_input("Password", type="password", key="li_pw")
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            submitted = st.form_submit_button("Login")
    if submitted:
        student = find_student(data, netid) if netid.strip() else None
        if student is not None and pw and str(student["Password"]) == pw:
            st.session_state.authenticated = True
            st.session_state.username = str(student["NetID"])
            st.session_state.page = "role"
            st.session_state.pending_toast = f"Welcome, {student['First_Name'] or student['NetID']}!"
            st.rerun()
        else:
            st.warning("That NetID and password don't match. Check them or create an account below.")

    with st.expander("New here? Create an account"):
        codes = list(data["classes"].keys())
        with st.form("signup_form", border=False):
            n_id = st.text_input("NetID", key="su_netid")
            n_pw = st.text_input("Create a password", type="password", key="su_pw")
            c1, c2 = st.columns(2)
            first = c1.text_input("First name", key="su_first")
            last = c2.text_input("Last name", key="su_last")
            c3, c4 = st.columns(2)
            gender = c3.selectbox("Gender", ["Female", "Male", "Other"], key="su_gender")
            end = academic_end_year()
            grad = c4.selectbox("Grad year", list(range(end, end + 5)), key="su_grad")
            major = st.text_input("Major", placeholder="e.g. Computer Science", key="su_major")
            picks = st.multiselect("Your courses", codes, format_func=lambda c: course_label(data, c), key="su_courses")
            bio = st.text_area("Short bio (optional)", max_chars=200, key="su_bio")
            created = st.form_submit_button("Create Account")
        if created:
            nid = n_id.strip().lower()
            if not (nid and n_pw and first.strip() and last.strip() and major.strip()):
                st.warning("Fill in your NetID, password, name and major.")
            elif not re.fullmatch(r"[a-z]{1,4}\d{1,6}", nid):
                st.warning("A NetID looks like 'ab1234' (letters followed by numbers).")
            elif find_student(data, nid) is not None:
                st.warning("That NetID already has an account. Use Login above.")
            else:
                row = {c: "" for c in data["Students"].columns}
                row.update({"NetID": nid, "Password": n_pw, "Last_Name": last.strip(), "First_Name": first.strip(),
                            "Gender": gender, "Grad_Year": grad, "Major": major.strip()})
                if register_student(data, row):
                    for code in picks:
                        enroll(data, nid, code)
                    if bio.strip():
                        save_bio(data, nid, bio.strip())
                    st.session_state.authenticated = True
                    st.session_state.username = nid
                    st.session_state.page = "role"
                    st.session_state.pending_toast = "Account created. You're signed in!"
                    st.rerun()
                else:
                    st.warning("We couldn't save your account right now. Please try again.")


def screen_role(data: dict) -> None:
    brand()
    st.markdown(f'<div style="text-align:center">{PERSON_ICON}</div>', unsafe_allow_html=True)
    st.markdown('<div class="who">WHO A<b>R</b>E YOU?</div>', unsafe_allow_html=True)
    st.markdown('<div class="screen-sub">select your role to continue</div>', unsafe_allow_html=True)
    st.write("")
    if st.button("Student", key="role_student"):
        st.session_state.role = "Student"
        go("courses")
    st.write("")
    if st.button("Instructor", key="role_instructor"):
        st.session_state.role = "Instructor"
        go("instructor")
    st.write("")
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        if st.button("Log out", key="logout"):
            logout()
            st.rerun()


def screen_courses(data: dict) -> None:
    brand()
    title("Select Your Course", "Only courses with active group assignments are shown")
    mine = enrolled_courses(data, st.session_state.username)
    if not mine:
        st.info("You aren't enrolled in any course yet.")
    for code in mine:
        info = course_info(data, code)
        with st.container(key=f"course_{code}"):
            st.markdown(
                f"""<div class="course-t">{escape(course_label(data, code))}<br>
                {escape(str(info.get('Professor', '')))}<br>{escape(str(info.get('Section', '')))}</div>""",
                unsafe_allow_html=True,
            )
            if st.button("FIND PARTNER", key=f"find_{code}"):
                st.session_state.course = code
                go("filters")
    nav_bar()


def screen_filters(data: dict) -> None:
    brand()
    title("Filters")
    saved = st.session_state.filters

    st.markdown('<div class="f-head">Gender</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    g_male = c1.checkbox("Male", key="g_Male", value="Male" in saved["gender"])
    g_any = c2.checkbox("Any", key="g_Any", value="Any" in saved["gender"])
    g_female = c1.checkbox("Female", key="g_Female", value="Female" in saved["gender"])

    st.markdown('<div class="f-head">Year</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    y1 = c1.checkbox("1st", key="y_1st", value="1st" in saved["year"])
    y4 = c2.checkbox("4th", key="y_4th", value="4th" in saved["year"])
    y2 = c1.checkbox("2nd", key="y_2nd", value="2nd" in saved["year"])
    y3 = c2.checkbox("3rd", key="y_3rd", value="3rd" in saved["year"])

    st.markdown('<div class="f-head">Major</div>', unsafe_allow_html=True)
    with st.container(key="major_tiles"):
        c1, c2 = st.columns(2)
        m_bus = c1.checkbox("Business", key="m_Business", value="Business" in saved["major"])
        m_oth = c2.checkbox("Other", key="m_Other", value="Other" in saved["major"])
        m_stem = c1.checkbox("🧪 STEM", key="m_STEM", value="STEM" in saved["major"])
        m_art = c2.checkbox("🥁 Music / Arts", key="m_Arts", value="Music / Arts" in saved["major"])

    st.markdown('<div class="f-head">Attendance Habit</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    h_often = c1.checkbox("Often", key="h_Often", value="Often" in saved["habit"])
    h_rare = c2.checkbox("Rarely", key="h_Rarely", value="Rarely" in saved["habit"])
    h_some = c1.checkbox("Sometimes", key="h_Sometimes", value="Sometimes" in saved["habit"])

    st.write("")
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button("APPLY FILTERS", key="apply_filters"):
            st.session_state.filters = {
                "gender": [n for n, on in (("Male", g_male), ("Female", g_female), ("Any", g_any)) if on],
                "year": [n for n, on in (("1st", y1), ("2nd", y2), ("3rd", y3), ("4th", y4)) if on],
                "major": [n for n, on in (("Business", m_bus), ("STEM", m_stem), ("Music / Arts", m_art), ("Other", m_oth)) if on],
                "habit": [n for n, on in (("Often", h_often), ("Sometimes", h_some), ("Rarely", h_rare)) if on],
            }
            go("partners")
    nav_bar()


def screen_partners(data: dict) -> None:
    brand()
    code = st.session_state.course
    if not code or code not in data["classes"]:
        title("Available Partners")
        st.info("Choose a course first.")
        if st.button("BACK TO COURSES", key="pick_course"):
            go("courses", remember=False)
        return
    title("Available Partners", course_label(data, code))
    me = st.session_state.username
    pool = course_pool(data, code, me)
    matches = filter_pool(pool, st.session_state.filters)

    if matches.empty:
        st.info("No students match these filters. Go back and widen them, "
                "or leave a group unticked to include everyone.")
    for i, (_, row) in enumerate(matches.iterrows()):
        pending = has_request(data, me, row["NetID"], code)
        with st.container(key=f"pcard_{i}"):
            st.markdown(
                f"""<div class="pc"><div class="av">{AVATAR_SVG}</div>
                <div class="t">{escape(row['Short'])}{' · Pending' if pending else ''}<br>
                {escape(row['Group'])} - {YEAR_LABEL.get(row['Year'], row['Year'])}<br>
                Attendance: {row['Habit']}</div></div>""",
                unsafe_allow_html=True,
            )
            if st.button("View Profile", key=f"view_{row['NetID']}"):
                st.session_state.selected = row["NetID"]
                go("profile")

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button("back to courses", key="back_courses"):
            st.session_state.history = ["role"]
            go("courses", remember=False)
    nav_bar()


def screen_profile(data: dict) -> None:
    brand()
    title("Student Profile", "viewing profile")
    code = st.session_state.course
    me = st.session_state.username
    pool = course_pool(data, code, me) if code else pd.DataFrame()
    hit = pool[pool["NetID"] == st.session_state.selected] if len(pool) else pool
    if hit.empty:
        st.info("Pick a student from the results to see their profile.")
        if st.button("BACK TO RESULTS", key="profile_back"):
            go("partners", remember=False)
        return
    p = hit.iloc[0]
    bio = f'<div class="bio">{escape(str(p["Bio"]))}</div>' if str(p["Bio"]).strip() else ""
    st.markdown(
        f"""<div class="profile-card"><div class="av">{AVATAR_SVG}</div>
        <div class="nm">{escape(p['Name'])}</div>
        <div class="ln">Major: {escape(p['Group'])}</div>
        <div class="ln">Year: {YEAR_LABEL.get(p['Year'], p['Year'])}</div>
        <div class="ln">Attendance: {p['Habit']}</div>
        <div class="looking">Looking for: Partner</div>{bio}</div>""",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if has_request(data, me, p["NetID"], code):
            pass
        elif st.button("Send Request", key="send_request"):
            if add_request(data, me, p["NetID"], code):
                go("sent")
            else:
                st.warning("We couldn't send your request right now. Please try again.")
    if has_request(data, me, p["NetID"], code):
        if st.button("BACK TO RESULTS", key="profile_back"):
            st.session_state.history = ["role", "courses", "filters"]
            go("partners", remember=False)
    nav_bar()


def screen_sent(data: dict) -> None:
    brand()
    st.write("")
    st.markdown(
        """<div class="sent-card"><div class="h">Request Sent!</div>
        <div class="p">Your request has been sent.</div>
        <div class="status">Status: Pending</div>
        <div class="p">Once accepted, you can find your partner's email through canvas inbox.</div></div>""",
        unsafe_allow_html=True,
    )
    if st.button("BACK TO RESULTS", key="sent_back"):
        st.session_state.history = ["role", "courses", "filters"]
        go("partners", remember=False)
    nav_bar()


def screen_instructor(data: dict) -> None:
    brand()
    title("Instructor View", "attendance and partner requests by course")
    if not data["classes"]:
        st.info("No course tables found yet.")
    for code, df in data["classes"].items():
        att = parse_attendance(df["Attendance"]) if len(df) else pd.Series(dtype=int)
        reqs = data["Requests"]
        n_req = int((reqs["Course"] == code).sum())
        with st.container(key=f"course_{code}"):
            st.markdown(f'<div class="course-t">{escape(course_label(data, code))}</div>', unsafe_allow_html=True)
            a, b, c = st.columns(3)
            a.metric("Students", len(df))
            b.metric("Avg. attend.", f"{int(att.mean()) if len(att) else 0}%")
            c.metric("Requests", n_req)
    nav_bar()


SCREENS = {
    "role": screen_role,
    "courses": screen_courses,
    "filters": screen_filters,
    "partners": screen_partners,
    "profile": screen_profile,
    "sent": screen_sent,
    "instructor": screen_instructor,
}


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    seed_demo_files()
    init_state()
    inject_css()
    data = load_data()

    if st.session_state.pending_toast:
        st.toast(st.session_state.pending_toast, icon="✅")
        st.session_state.pending_toast = None

    if not st.session_state.authenticated:
        screen_login(data)
        return
    if find_student(data, st.session_state.username) is None:
        logout()
        st.rerun()
        return
    SCREENS.get(st.session_state.page, screen_role)(data)


main()
