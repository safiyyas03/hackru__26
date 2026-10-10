import os
import pandas as pd
from flask import Flask, request, jsonify, session
from flask_cors import CORS

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "local-development-only-change-me"
)

# Allow frontend development server
CORS(
    app,
    origins=["http://localhost:3000", "http://localhost:5173"],
    supports_credentials=True
)

EXCEL_FILE = "students.xlsx"


def get_students():
    df = pd.read_excel(EXCEL_FILE, dtype=str)
    df.columns = df.columns.str.strip()
    return df.fillna("NA")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    netid = data.get("netid", "").strip()
    password = data.get("password", "")

    if not netid or not password:
        return jsonify({
            "success": False,
            "message": "NetID and password required"
        }), 400

    df = get_students()

    student = df[
        (df["NetID"] == netid) &
        (df["Password"] == password)
    ]

    if student.empty:
        return jsonify({
            "success": False,
            "message": "Invalid NetID or password"
        }), 401

    user = student.iloc[0]

    session.clear()
    session["netid"] = user["NetID"]

    return jsonify({
        "success": True,
        "message": "Login successful",
        "student": {
            "netid": user["NetID"],
            "first_name": user["First_Name"],
            "last_name": user["Last_Name"]
        }
    }), 200


@app.route("/api/student", methods=["GET"])
def student_info():
    if "netid" not in session:
        return jsonify({
            "success": False,
            "message": "Not authenticated"
        }), 401

    df = get_students()
    student = df[df["NetID"] == session["netid"]]

    if student.empty:
        session.clear()
        return jsonify({
            "success": False,
            "message": "Student not found"
        }), 404

    user = student.iloc[0]

    return jsonify({
        "netid": user["NetID"],
        "first_name": user["First_Name"],
        "last_name": user["Last_Name"],
        "gender": user["Gender"],
        "grad_year": user["Grad_Year"],
        "major": user["Major"],
        "attendance": user["Attendence"]
    }), 200


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    }), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)
