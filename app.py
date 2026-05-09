from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client
import os
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# SUPABASE
supabase = create_client(
    "https://xxxxx.supabase.co",  # ta vraie URL
    "ta_vraie_anon_key"           # ta vraie clé
)
FEE_PERCENT = 0.07
RATES = {
    "RDC_TO_KEN": 129.50,
    "KEN_TO_RDC": 0.00772
}

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

    result = supabase.table("transactions").insert({
        "sender_name": data['senderName'],
        "sender_phone": data['senderPhone'],
        "receiver_name": data['receiverName'],
        "receiver_phone": data['receiverPhone'],
        "amount_sent": amount,
        "fees": fees,
        "amount_received": amount_received,
        "direction": direction,
        "status": "PENDING"
    }).execute()

    return jsonify(result.data[0]), 201

@app.route('/transfer/<transaction_id>', methods=['GET'])
def get_transfer(transaction_id):
    result = supabase.table("transactions").select("*").eq("id", transaction_id).execute()
    if not result.data:
        return jsonify({"error": "Transaction introuvable"}), 404
    return jsonify(result.data[0]), 200

@app.route('/transactions', methods=['GET'])
def get_all_transactions():
    result = supabase.table("transactions").select("*").order("created_at", desc=True).execute()
    return jsonify(result.data), 200

@app.route('/rates', methods=['GET'])
def get_rates():
    return jsonify(RATES), 200

@app.route('/debug')
def debug():
    return jsonify({
        "supabase_url": os.environ.get("SUPABASE_URL", "NON TROUVÉ"),
        "supabase_key": "OK" if os.environ.get("SUPABASE_KEY") else "NON TROUVÉ"
    })
