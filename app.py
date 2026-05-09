from flask import Flask, jsonify
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

@app.route('/')
def home():
    return "MuniaPay Backend Live 🚀"

@app.route('/transactions')
def transactions():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("SELECT * FROM transactions")

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(rows)
