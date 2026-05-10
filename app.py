from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client
import os
import uuid
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

# SUPABASE
supabase = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# PAWAPAY
PAWAPAY_URL = "https://api.sandbox.pawapay.cloud"
PAWAPAY_TOKEN = os.environ.get("PAWAPAY_TOKEN")

FEE_PERCENT = 0.07
RATES = {
    "RDC_TO_KEN": 129.50,
    "KEN_TO_RDC": 0.00772
}

CORRESPONDENTS = {
    "RDC_TO_KEN": {"deposit": "AIRTEL_MONEY_CD", "payout": "MPESA_KE"},
    "KEN_TO_RDC": {"deposit": "MPESA_KE", "payout": "AIRTEL_MONEY_CD"}
}

CURRENCIES = {
    "RDC_TO_KEN": {"deposit": "CDF", "payout": "KES"},
    "KEN_TO_RDC": {"deposit": "KES", "payout": "CDF"}
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
    transaction_id = str(uuid.uuid4())

    # 1. Créer en DB
    supabase.table("transactions").insert({
        "id": transaction_id,
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

    # 2. Initier le dépôt Pawapay
    deposit_response = requests.post(
        f"{PAWAPAY_URL}/deposits",
        json={
            "depositId": transaction_id,
            "amount": str(amount),
            "currency": CURRENCIES[direction]["deposit"],
            "correspondent": CORRESPONDENTS[direction]["deposit"],
            "payer": {
                "type": "MSISDN",
                "address": {"value": data['senderPhone']}
            },
            "statementDescription": f"MuniaPay {transaction_id[:8]}"
        },
        headers={
            "Authorization": f"Bearer {PAWAPAY_TOKEN}",
            "Content-Type": "application/json"
        }
    )

    # 3. Mettre à jour le statut
    supabase.table("transactions").update(
        {"status": "COLLECTING"}
    ).eq("id", transaction_id).execute()

    return jsonify({
        "id": transaction_id,
        "status": "COLLECTING",
        "amountSent": amount,
        "amountReceived": amount_received,
        "fees": fees
    }), 201


@app.route('/webhook/deposit', methods=['POST'])
def webhook_deposit():
    data = request.get_json()
    deposit_id = data.get("depositId")
    status = data.get("status")

    if status == "COMPLETED":
        # Récupérer la transaction
        result = supabase.table("transactions").select("*").eq("id", deposit_id).execute()
        if not result.data:
            return jsonify({"error": "Transaction introuvable"}), 404

        transaction = result.data[0]

        # Mettre à jour le statut
        supabase.table("transactions").update(
            {"status": "SENDING"}
        ).eq("id", deposit_id).execute()

        # Initier le payout
        requests.post(
            f"{PAWAPAY_URL}/payouts",
            json={
                "payoutId": str(uuid.uuid4()),
                "amount": str(transaction["amount_received"]),
                "currency": CURRENCIES[transaction["direction"]]["payout"],
                "correspondent": CORRESPONDENTS[transaction["direction"]]["payout"],
                "recipient": {
                    "type": "MSISDN",
                    "address": {"value": transaction["receiver_phone"]}
                },
                "statementDescription": f"MuniaPay {deposit_id[:8]}"
            },
            headers={
                "Authorization": f"Bearer {PAWAPAY_TOKEN}",
                "Content-Type": "application/json"
            }
        )

    elif status == "FAILED":
        supabase.table("transactions").update(
            {"status": "FAILED"}
        ).eq("id", deposit_id).execute()

    return jsonify({"status": "ok"}), 200


@app.route('/webhook/payout', methods=['POST'])
def webhook_payout():
    data = request.get_json()
    payout_id = data.get("payoutId")
    status = data.get("status")

    if status == "COMPLETED":
        supabase.table("transactions").update(
            {"status": "COMPLETED"}
        ).eq("id", payout_id).execute()

    elif status == "FAILED":
        supabase.table("transactions").update(
            {"status": "FAILED"}
        ).eq("id", payout_id).execute()

    return jsonify({"status": "ok"}), 200


@app.route('/webhook/refund', methods=['POST'])
def webhook_refund():
    return jsonify({"status": "ok"}), 200


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
