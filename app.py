@app.route('/transfer', methods=['POST'])
def create_transfer():

    try:

        data = request.get_json()

        required = [
            'senderName',
            'senderPhone',
            'receiverName',
            'receiverPhone',
            'amount',
            'direction'
        ]

        for field in required:
            if not data.get(field):
                return jsonify({
                    "error": f"Champ manquant : {field}"
                }), 400

        direction = data['direction']

        if direction not in RATES:
            return jsonify({
                "error": "Direction invalide"
            }), 400

        amount = float(data['amount'])

        if amount <= 0:
            return jsonify({
                "error": "Montant invalide"
            }), 400

        fees = amount * FEE_PERCENT
        net = amount - fees
        amount_received = net * RATES[direction]

        transaction_id = str(uuid.uuid4())

        transaction = {
            "id": transaction_id,
            "senderName": data['senderName'],
            "senderPhone": data['senderPhone'],
            "receiverName": data['receiverName'],
            "receiverPhone": data['receiverPhone'],
            "amountSent": amount,
            "fees": round(fees, 2),
            "amountReceived": round(amount_received, 2),
            "direction": direction,
            "status": "PENDING",
            "createdAt": datetime.utcnow().isoformat()
        }

        transactions[transaction_id] = transaction

        return jsonify(transaction), 201

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500
