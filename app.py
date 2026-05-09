from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app, origins=["https://ton-frontend.com"])

# --- CONSTANTES ---
FEE_PERCENT = 0.07
RATES = {
    "RDC_TO_KEN": 129.50,
    "KEN_TO_RDC": 0.00772
}

# --- STOCKAGE TEMPORAIRE (avant Supabase) ---
transactions = {}

# --- ROUTES ---

@app.route('/')
def home():
    return "MuniaPay Backend Live 🚀"


@app.route('/transfer', methods=['POST'])
def create_transfer():
    data = request.get_json()

    # Validation
    required = ['senderName', 'senderPhone', 'receiverName', 'receiverPhone', 'amount', 'direction']
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Champ manquant : {field}"}), 400

    direction = data['direction']
    if direction not in RATES:
        return jsonify({"error": "Direction invalide"}), 400

    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({"error": "Montant invalide"}), 400

    # Calcul
    fees = amount * FEE_PERCENT
    net = amount - fees
    amount_received = net * RATES[direction]

    # Création transaction
    transaction_id = str(uuid.uuid4())
    transaction = {
        "id": transaction_id,
        "senderName": data['senderName'],
        "senderPhone": data['senderPhone'],
        "receiverName": data['receiverName'],
        "receiverPhone": data['receiverPhone'],
        "amountSent": amount,
        "fees": fees,
        "amountReceived": round(amount_received, 2),
        "direction": direction,
        "status": "PENDING",
        "createdAt": datetime.utcnow().isoformat()
    }

    transactions[transaction_id] = transaction

    return jsonify(transaction), 201


@app.route('/transfer/<transaction_id>', methods=['GET'])
def get_transfer(transaction_id):
    transaction = transactions.get(transaction_id)
    if not transaction:
        return jsonify({"error": "Transaction introuvable"}), 404
    return jsonify(transaction), 200


@app.route('/transactions', methods=['GET'])
def get_all_transactions():
    return jsonify(list(transactions.values())), 200


@app.route('/rates', methods=['GET'])
def get_rates():
    return jsonify(RATES), 200
