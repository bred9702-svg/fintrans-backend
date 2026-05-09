from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import psycopg2
from datetime import datetime
import uuid

# 1. APP EN PREMIER — toujours
app = Flask(__name__)
CORS(app)

# 2. CONNEXION DB
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)

# 3. CONSTANTES
FEE_PERCENT = 0.07
RATES = {
    "RDC_TO_KEN": 129.50,
    "KEN_TO_RDC": 0.00772
}

# 4. ROUTES ENSUITE
@app.route('/')
def home():
    return "MuniaPay Backend Live 🚀"

@app.route('/transfer', methods=['POST'])
def create_transfer():
    data = request.get_json()

    required = ['senderName', 'senderPhone', 'receiverName', 'receiverPhone', 'amount', 'direction']
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Champ manquant : {field}"}), 400

    direction = data['direction']
    if direction not in RATES:
        return jsonify({"error": "Direction invalide"}), 400

    amount = float(data['amount'])
    fees = round(amount * FEE_PERCENT, 2)
    net = amount - fees
    amount_received = round(net * RATES[direction], 2)
    transaction_id = str(uuid.uuid4())

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions 
        (id, sender_name, sender_phone, receiver_name, receiver_phone, amount_sent, fees, amount_received, direction, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        transaction_id,
        data['senderName'], data['senderPhone'],
        data['receiverName'], data['receiverPhone'],
        amount, fees, amount_received,
        direction, 'PENDING',
        datetime.utcnow()
    ))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "id": transaction_id,
        "status": "PENDING",
        "amountSent": amount,
        "amountReceived": amount_received,
        "fees": fees,
        "direction": direction
    }), 201

@app.route('/transfer/<transaction_id>', methods=['GET'])
def get_transfer(transaction_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Transaction introuvable"}), 404

    return jsonify({"id": row[0], "status": row[9]}), 200

@app.route('/transactions', methods=['GET'])
def get_all_transactions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"id": r[0], "status": r[9], "amountSent": r[5]} for r in rows]), 200
