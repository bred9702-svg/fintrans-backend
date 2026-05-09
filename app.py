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
    try:
        conn = psycopg2.connect(DATABASE_URL)

        cur = conn.cursor()

        cur.execute("SELECT * FROM transactions")

        rows = cur.fetchall()

        transactions = []

        for row in rows:
            transactions.append({
                "id": str(row[0]),
                "sender_name": row[1],
                "sender_phone": row[2],
                "receiver_name": row[3],
                "receiver_phone": row[4],
                "amount": float(row[5]),
                "direction": row[6],
                "status": row[7],
                "created_at": str(row[8])
            })

        cur.close()
        conn.close()

        return jsonify(transactions)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
        
