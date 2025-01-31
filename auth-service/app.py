from flask import Flask, request, jsonify
from services.cognito_service import CognitoService
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Permite chamadas de outros domínios (frontend)

cognito_service = CognitoService()

@app.route("/check-email", methods=["POST", "OPTIONS"])
def check_email():
    if request.method == "OPTIONS":
        return '', 200  # Responde ao método OPTIONS com status 200

    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "E-mail é obrigatório."}), 400

    try:
        response = cognito_service.check_email_exists(email)
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/register", methods=["POST", "OPTIONS"])
def register():
    if request.method == "OPTIONS":
        return '', 200  # Responde ao método OPTIONS com status 200

    data = request.json
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    if not email or not password or not name:
        return jsonify({"error": "Todos os campos são obrigatórios."}), 400

    try:
        response = cognito_service.sign_up(email, password, name)
        return jsonify({"message": "Usuário registrado com sucesso!", "data": response}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/verify", methods=["POST", "OPTIONS"])
def verify():
    if request.method == "OPTIONS":
        return '', 200  # Responde ao método OPTIONS com status 200

    data = request.json
    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({"error": "E-mail e código são obrigatórios."}), 400

    try:
        response = cognito_service.confirm_sign_up(email, code)
        return jsonify({"message": "E-mail verificado com sucesso!", "data": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return '', 200  # Responde ao método OPTIONS com status 200

    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "E-mail e senha são obrigatórios."}), 400

    try:
        # Tenta autenticar o usuário via Cognito
        response = cognito_service.login(email, password)
        return jsonify({"message": "Login realizado com sucesso!", "user": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/logout", methods=["POST", "OPTIONS"])
def logout():
    if request.method == "OPTIONS":
        return '', 200  # Responde ao método OPTIONS com status 200

    data = request.json
    access_token = data.get("access_token")

    if not access_token:
        return jsonify({"error": "Token de acesso é obrigatório."}), 400

    try:
        response = cognito_service.logout(access_token)
        return jsonify({"message": "Logout realizado com sucesso!", "data": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/user", methods=["GET", "OPTIONS"])
def get_user():
    if request.method == "OPTIONS":
        return '', 200  # Responde ao método OPTIONS com status 200

    access_token = request.headers.get("Authorization")

    if not access_token:
        return jsonify({"error": "Token de acesso é obrigatório."}), 400

    try:
        response = cognito_service.get_user(access_token)
        return jsonify({"message": "Usuário recuperado com sucesso!", "data": response}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True)

