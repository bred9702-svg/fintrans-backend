import os
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
)

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client
import uuid
import requests
import re
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app, origins=["https://muniapay-frontend.vercel.app"])

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)

# SUPABASE
supabase = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# PAWAPAY
PAWAPAY_URL = "https://api.sandbox.pawapay.cloud"
PAWAPAY_TOKEN = os.environ.get("PAWAPAY_TOKEN")
CHECK_BALANCE = os.environ.get("CHECK_BALANCE", "false").lower() == "true"
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")

# Timeout pour toutes les requetes Pawapay
PAWAPAY_TIMEOUT = 10

FEE_PERCENT = 0.07

def get_live_rates():
    """Recupere les taux de change en temps reel depuis l'API"""
    try:
        response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        if response.status_code == 200:
            data = response.json()
            usd_to_kes = data["rates"]["KES"]
            return {
                "RDC_TO_KEN": usd_to_kes,
                "KEN_TO_RDC": 1 / usd_to_kes
            }
    except Exception as e:
        print(f"Erreur API exchange rates: {e}")
    
    return {
        "RDC_TO_KEN": 129.50,
        "KEN_TO_RDC": 0.00772
    }

RATES = get_live_rates()

CORRESPONDENTS = {
    "RDC_TO_KEN": {"deposit": "AIRTEL_COD", "payout": "MPESA_KEN"},
    "KEN_TO_RDC": {"deposit": "MPESA_KEN", "payout": "AIRTEL_COD"}
}

CURRENCIES = {
    "RDC_TO_KEN": {"deposit": "USD", "payout": "KES"},
    "KEN_TO_RDC": {"deposit": "KES", "payout": "USD"}
}

FAILURE_MESSAGES = {
    "AUTHENTICATION_ERROR": "PIN incorrect. Veuillez recommencer.",
    "INSUFFICIENT_BALANCE": "Solde insuffisant sur le compte Mobile Money.",
    "PAYER_LIMIT_REACHED": "Limite de transfert atteinte sur votre compte Mobile Money.",
    "PAYEE_NOT_FOUND": "Le numero du beneficiaire n'a pas de compte Mobile Money.",
    "PAYER_NOT_FOUND": "Votre numero n'a pas de compte Mobile Money.",
    "TRANSACTION_ALREADY_IN_PROCESS": "Une transaction est deja en cours sur ce numero.",
    "TIMEOUT": "Delai depasse. La confirmation n'a pas ete recue a temps.",
    "PROVIDER_TEMPORARILY_UNAVAILABLE": "L'operateur Mobile Money est temporairement indisponible.",
    "OTHER": "Une erreur est survenue. Veuillez reessayer ou contacter le support."
}

def mask_phone(phone):
    """Masque un numero de telephone pour les logs"""
    if not phone or len(phone) < 6:
        return "***"
    return phone[:3] + "***" + phone[-3:]

def mask_data(data):
    """Masque les donnees sensibles avant logging"""
    if not isinstance(data, dict):
        return data
    
    masked = {}
    sensitive_keys = ["senderPhone", "receiverPhone", "phone", "msisdn"]
    
    for key, value in data.items():
        if key in sensitive_keys and isinstance(value, str):
            masked[key] = mask_phone(value)
        elif isinstance(value, dict):
            masked[key] = mask_data(value)
        else:
            masked[key] = value
    return masked

def require_admin_key(func):
    """Decorateur pour proteger les endpoints admin"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("X-Admin-Key")
        if not ADMIN_API_KEY or auth_header != ADMIN_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)
    return wrapper

@app.route('/')
def home():
    return "MuniaPay Backend Live"

@app.route('/transfer', methods=['POST'])
@limiter.limit("10 per minute")
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
    
    # Validation du montant
    if amount <= 0:
        return jsonify({"error": "Montant invalide"}), 400
    
    if amount < 5:
        return jsonify({"error": "Montant minimum : 5 USD (ou equivalent)"}), 400
    
    max_amount = 500 if direction == "RDC_TO_KEN" else 500 * 129.50
    if amount > max_amount:
        return jsonify({"error": "Montant maximum depasse"}), 400
    
    # Validation des numeros de telephone
    if direction == "RDC_TO_KEN":
        if not re.match(r'^243[0-9]{9}$', data['senderPhone']):
            return jsonify({"error": "Numero expediteur invalide (format: 243XXXXXXXXX)"}), 400
        if not re.match(r'^254[0-9]{9}$', data['receiverPhone']):
            return jsonify({"error": "Numero beneficiaire invalide (format: 254XXXXXXXXX)"}), 400
    else:
        if not re.match(r'^254[0-9]{9}$', data['senderPhone']):
            return jsonify({"error": "Numero expediteur invalide (format: 254XXXXXXXXX)"}), 400
        if not re.match(r'^243[0-9]{9}$', data['receiverPhone']):
            return jsonify({"error": "Numero beneficiaire invalide (format: 243XXXXXXXXX)"}), 400
    
    fees = round(amount * FEE_PERCENT, 2)
    net = amount - fees
    amount_received = round(net * RATES[direction], 2)
    transaction_id = str(uuid.uuid4())

    # 1. Creer en DB
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

    # 2. Verifier le solde du wallet destination (seulement si CHECK_BALANCE est activee)
    if CHECK_BALANCE:
        payout_currency = CURRENCIES[direction]["payout"]
        
        try:
            balance_response = requests.get(
                f"{PAWAPAY_URL}/v2/wallet-balances",
                headers={"Authorization": f"Bearer {PAWAPAY_TOKEN}"},
                timeout=PAWAPAY_TIMEOUT
            )
            
            if balance_response.status_code == 200:
                balances = balance_response.json()
                wallets = balances.get("balances", [])
                payout_wallet = next((w for w in wallets if w.get("currency") == payout_currency), None)
                
                if payout_wallet:
                    available = float(payout_wallet.get("balance", 0))
                    if available < amount_received:
                        supabase.table("transactions").update({
                            "status": "FAILED",
                            "failure_reason": "Service temporairement indisponible."
                        }).eq("id", transaction_id).execute()
                        
                        return jsonify({
                            "id": transaction_id,
                            "status": "FAILED",
                            "error": "INSUFFICIENT_LIQUIDITY",
                            "message": "Service temporairement indisponible."
                        }), 503
        except requests.Timeout:
            print("Timeout lors du check de balance")

    # 3. Initier le depot Pawapay
    try:
        deposit_response = requests.post(
            f"{PAWAPAY_URL}/deposits",
            json={
                "depositId": transaction_id,
                "customerTimestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "amount": str(int(amount)) if CORRESPONDENTS[direction]["deposit"] == "MPESA_KEN" else str(amount),
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
            },
            timeout=PAWAPAY_TIMEOUT
        )

        print("=== PAWAPAY DEPOSIT RESPONSE ===")
        print("Status:", deposit_response.status_code)
        print("================================")
    except requests.Timeout:
        print("Timeout Pawapay deposit")
        return jsonify({"error": "Service temporairement indisponible."}), 504
    except Exception as e:
        print(f"Erreur Pawapay deposit: {type(e).__name__}")
        return jsonify({"error": "Erreur lors de la creation du transfert."}), 500

    # 4. Mettre a jour le statut
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
    print("=== WEBHOOK DEPOSIT ===")
    print("Body:", mask_data(data))
    print("=======================")
    
    deposit_id = data.get("depositId")
    status = data.get("status")

    # Idempotency : verifier l'etat actuel avant de traiter
    result = supabase.table("transactions").select("*").eq("id", deposit_id).execute()
    if not result.data:
        return jsonify({"error": "Transaction introuvable"}), 404
    
    transaction = result.data[0]
    current_status = transaction["status"]

    if status == "COMPLETED":
        # Ne traiter que si on est encore au stade COLLECTING
        if current_status != "COLLECTING":
            print(f"Ignored: transaction {deposit_id} already in status {current_status}")
            return jsonify({"status": "ignored"}), 200
        
        # Mettre a jour le statut
        supabase.table("transactions").update(
            {"status": "SENDING"}
        ).eq("id", deposit_id).execute()

        # Generer un ID unique pour le payout et le stocker
        payout_id = str(uuid.uuid4())
        supabase.table("transactions").update(
            {"payout_id": payout_id}
        ).eq("id", deposit_id).execute()

        # Initier le payout
        try:
            payout_response = requests.post(
                f"{PAWAPAY_URL}/payouts",
                json={
                    "payoutId": payout_id,
                    "customerTimestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "amount": str(int(transaction["amount_received"])) if CORRESPONDENTS[transaction["direction"]]["payout"] == "MPESA_KEN" else str(transaction["amount_received"]),
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
                },
                timeout=PAWAPAY_TIMEOUT
            )
            print("=== PAYOUT INITIATED ===")
            print("Status:", payout_response.status_code)
            print("========================")
        except requests.Timeout:
            print("Timeout Pawapay payout")
            supabase.table("transactions").update({
                "status": "FAILED",
                "failure_reason": "Timeout lors de l'envoi. Un remboursement automatique sera effectue."
            }).eq("id", deposit_id).execute()
        except Exception as e:
            print(f"Erreur Pawapay payout: {type(e).__name__}")

    elif status == "FAILED":
        # Idempotency
        if current_status in ["FAILED", "REFUNDED"]:
            return jsonify({"status": "ignored"}), 200
        
        failure_reason_code = data.get("failureReason", {}).get("failureCode", "OTHER")
        failure_message = FAILURE_MESSAGES.get(failure_reason_code, FAILURE_MESSAGES["OTHER"])
        
        supabase.table("transactions").update({
            "status": "FAILED",
            "failure_reason": failure_message
        }).eq("id", deposit_id).execute()

    return jsonify({"status": "ok"}), 200


@app.route('/webhook/payout', methods=['POST'])
def webhook_payout():
    data = request.get_json()
    print("=== WEBHOOK PAYOUT ===")
    print("Body:", mask_data(data))
    print("======================")
    
    payout_id = data.get("payoutId")
    status = data.get("status")

    # Retrouver la transaction via payout_id
    result = supabase.table("transactions").select("*").eq("payout_id", payout_id).execute()
    if not result.data:
        print(f"Transaction non trouvee pour payout_id: {payout_id}")
        return jsonify({"status": "ok"}), 200
    
    transaction = result.data[0]
    transaction_id = transaction["id"]
    current_status = transaction["status"]

    if status == "COMPLETED":
        # Idempotency : ne traiter que si en SENDING
        if current_status != "SENDING":
            print(f"Ignored: transaction {transaction_id} already in status {current_status}")
            return jsonify({"status": "ignored"}), 200
        
        supabase.table("transactions").update(
            {"status": "COMPLETED"}
        ).eq("id", transaction_id).execute()

    elif status == "FAILED":
        # Idempotency
        if current_status in ["FAILED", "REFUNDED"]:
            return jsonify({"status": "ignored"}), 200
        
        failure_reason_code = data.get("failureReason", {}).get("failureCode", "OTHER")
        failure_message = FAILURE_MESSAGES.get(failure_reason_code, FAILURE_MESSAGES["OTHER"])
        
        # Initier le refund automatique
        refund_id = str(uuid.uuid4())
        try:
            refund_response = requests.post(
                f"{PAWAPAY_URL}/refunds",
                json={
                    "refundId": refund_id,
                    "depositId": transaction_id,
                    "amount": str(transaction["amount_sent"]),
                    "metadata": [
                        {"fieldName": "reason", "fieldValue": f"Payout failed: {failure_reason_code}"}
                    ]
                },
                headers={
                    "Authorization": f"Bearer {PAWAPAY_TOKEN}",
                    "Content-Type": "application/json"
                },
                timeout=PAWAPAY_TIMEOUT
            )
            print("=== REFUND INITIATED ===")
            print("Status:", refund_response.status_code)
            print("========================")
        except requests.Timeout:
            print("Timeout Pawapay refund")
        except Exception as e:
            print(f"Erreur Pawapay refund: {type(e).__name__}")
        
        supabase.table("transactions").update({
            "status": "FAILED",
            "failure_reason": failure_message + " Un remboursement automatique est en cours."
        }).eq("id", transaction_id).execute()

    return jsonify({"status": "ok"}), 200


@app.route('/webhook/refund', methods=['POST'])
def webhook_refund():
    data = request.get_json()
    print("=== WEBHOOK REFUND ===")
    print("Body:", mask_data(data))
    print("======================")
    
    deposit_id = data.get("depositId")
    status = data.get("status")
    
    if not deposit_id:
        return jsonify({"status": "ok"}), 200
    
    # Idempotency
    result = supabase.table("transactions").select("*").eq("id", deposit_id).execute()
    if not result.data:
        return jsonify({"status": "ok"}), 200
    
    current_status = result.data[0]["status"]
    if current_status == "REFUNDED":
        return jsonify({"status": "ignored"}), 200
    
    if status == "COMPLETED":
        supabase.table("transactions").update({
            "status": "REFUNDED",
            "failure_reason": "Remboursement effectue avec succes."
        }).eq("id", deposit_id).execute()
    
    return jsonify({"status": "ok"}), 200


@app.route('/transfer/<transaction_id>', methods=['GET'])
def get_transfer(transaction_id):
    result = supabase.table("transactions").select("*").eq("id", transaction_id).execute()
    if not result.data:
        return jsonify({"error": "Transaction introuvable"}), 404
    return jsonify(result.data[0]), 200


@app.route('/transactions', methods=['GET'])
@require_admin_key
def get_all_transactions():
    result = supabase.table("transactions").select("*").order("created_at", desc=True).execute()
    return jsonify(result.data), 200


@app.route('/rates', methods=['GET'])
def get_rates():
    return jsonify(RATES), 200

@app.route('/sentry-test')
def sentry_test():
    raise Exception("Test Sentry - cette erreur est volontaire")
