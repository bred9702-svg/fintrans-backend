from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATABASE_URL = "postgresql://postgres:Ropitrasecure2026@db.hxydrsiwcnhvbmmntwqw.supabase.co:5432/postgres"

engine = create_engine(DATABASE_URL)

@app.route('/')
def home():
    return "MuniaPay Backend Live 🚀"

@app.route('/transactions', methods=['GET'])
def get_transactions():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT * FROM transactions"))

            transactions = []

            for row in result:
                transactions.append({
                    "id": str(row.id),
                    "sender_name": row.sender_name,
                    "sender_phone": row.sender_phone,
                    "receiver_name": row.receiver_name,
                    "receiver_phone": row.receiver_phone,
                    "amount": float(row.amount),
                    "direction": row.direction,
                    "status": row.status,
                    "created_at": str(row.created_at)
                })

        return jsonify(transactions), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
