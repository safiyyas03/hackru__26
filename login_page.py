from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # Needed for session management

EXCEL_FILE = 'users.xlsx'

@app.route('/')
def home():
    # Renders your HTML login page (expects login.html in a 'templates' folder)
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    netid = request.form.get('netid')
    password = request.form.get('password')
    
    if not os.path.exists(EXCEL_FILE):
        return "Database file not found!", 500
    
    # Read the Excel file
    df = pd.read_excel(EXCEL_FILE)
    
    # Check if netid and password match any row
    # (Ensure column names in Excel match 'netid' and 'password')
    user = df[(df['netid'].astype(str) == netid) & (df['password'].astype(str) == password)]
    
    if not user.empty:
        session['netid'] = netid
        return f"Login successful! Welcome back, {netid}."
    else:
        return render_template('login.html', error="Invalid NetID or Password")

@app.route('/logout')
def logout():
    session.pop('netid', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
