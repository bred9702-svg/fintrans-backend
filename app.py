from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- DATABASE CONNECTION ---
DATABASE_URL = "postgresql://postgres:Ropitrasecure2026@db.hxydrsiwcnhvbmmntwqw.supabase.co:5432/postgres"

engine = create_engine(DATABASE_URL)

# --- HOME ---
@app.route('/')
def home():
    return "MuniaPay Backend Live 🚀"

# --- INITIATE TRANSFER ---
@app.route('/initiate-transfer', methods=['POST'])
def initiate_transfer():
    try:
        data = request.get_json()

        sender_name = data.get('sender_name')
        sender_phone = data.get('sender_phone')
        receiver_name = data.get('receiver_name')
        receiver_phone = data.get('receiver_phone')
        amount = data.get('amount')
        direction = data.get('direction')

        # --- VALIDATION ---
        if not all([sender_name, sender_phone, receiver_name, receiver_phone, amount, direction]):
            return jsonify({
                "error": "Tous les champs sont obligatoires"
            }), 400

        transaction_id = str(uuid.uuid4())

        # --- SAVE TO DATABASE ---
        with engine.connect() as connection:
            connection.execute(text("""
                INSERT INTO transactions (
                    id,
                    sender_name,
                    sender_phone,
                    receiver_name,
                    receiver_phone,
                    amount,
                    direction,
                    status,
                    created_at
                )
                VALUES (
                    :id,
                    :sender_name,
                    :sender_phone,
                    :receiver_name,
                    :receiver_phone,
                    :amount,
                    :direction,
                    :status,
                    :created_at
                )
            """), {
                "id": transaction_id,
                "sender_name": sender_name,
                "sender_phone": sender_phone,
                "receiver_name": receiver_name,
                "receiver_phone": receiver_phone,
                "amount": amount,
                "direction": direction,
                "status": "pending",
                "created_at": datetime.utcnow()
            })

            connection.commit()

        return jsonify({
            "status": "pending",
            "transaction_id": transaction_id,
            "message": "Transaction enregistrée avec succès"
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# --- GET ALL TRANSACTIONS ---
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
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == '__main__':
    app.run()
