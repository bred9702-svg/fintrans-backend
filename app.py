from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "Backend Munia Pay actif 🚀"

@app.route('/initiate-transfer', methods=['POST'])
def initiate_transfer():
    data = request.get_json()

    sender_name = data.get('sender_name')
    sender_phone = data.get('sender_phone')
    receiver_name = data.get('receiver_name')
    receiver_phone = data.get('receiver_phone')
    amount = data.get('amount')
    direction = data.get('direction')

    # 🔥 LOGIQUE SIMPLIFIÉE (simulation)
    print("Nouvelle transaction :")
    print(sender_name, sender_phone, receiver_phone, amount, direction)

    return jsonify({
        "status": "pending",
        "message": "STK push envoyé (simulation)"
    }), 200


if __name__ == '__main__':
    app.run()
