from flask import Flask, request, jsonify
from flask_cors import CORS
from ticket_service.services.generate_qrcode_service import generate_qr_code
from ticket_service.services.generate_code_service import generate_code
from ticket_service.utils.db import *
from ticket_service.services.process_payment import *
import requests
from auth_service.services.cognito_service import CognitoService
import jwt

cognito_service = CognitoService()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
  # Habilita CORS para permitir requisições de outros domínios

@app.route('/generate_ticket', methods=['POST'])
def generate_ticket():
    data = request.json
    
    name = data.get('name')
    email = data.get('email')
    cpf = data.get('cpf')
    table = data.get('table')
    user_id = data.get('user_id')
    quantity = data.get('quantity', 1)  # Quantidade de tickets a serem gerados

    if not name or not email or not cpf or not table or not user_id:
        return jsonify({'error': 'Dados incompletos'}), 400

    tickets = []
    for _ in range(quantity):
        code = generate_code()
        init_db(table)

        if store_ticket(code, name, email, cpf, user_id, table):
            tickets.append({'code': code})
        else:
            return jsonify({'error': 'Código já existente'}), 409

    return jsonify({'tickets': tickets}), 201


@app.route('/tickets/<code>', methods=['GET'])
def read_ticket(code):
    table = request.args.get('table')  # Pega o nome da tabela do parâmetro de consulta
    ticket = get_ticket(code, table)
    
    if ticket:
        return jsonify({'code': ticket[0], 'name': ticket[1], 'email': ticket[2], 'cpf': ticket[3]}), 200
    else:
        return jsonify({'error': 'Ingresso não encontrado'}), 404

@app.route('/tickets', methods=['GET'])
def read_all_tickets():
    table = request.args.get('table', 'tickets')  # Pega o nome da tabela do parâmetro de consulta
    tickets = get_all_tickets(table)
    
    return jsonify([{'code': t[0], 'name': t[1], 'email': t[2], 'cpf': t[3], 'qr_code_path': t[4]} for t in tickets]), 200

@app.route('/tickets/<code>', methods=['PUT'])
def update_ticket_route(code):
    data = request.json
    table = data.get('table', 'tickets')  # Pega o nome da tabela do corpo da requisição
    name = data.get('name')
    email = data.get('email')
    cpf = data.get('cpf')

    if update_ticket(code, name=name, email=email, cpf=cpf, table=table):
        return jsonify({'message': 'Ingresso atualizado com sucesso'}), 200
    else:
        return jsonify({'error': 'Código não encontrado ou dados não alterados'}), 404

@app.route('/tickets/<code>', methods=['DELETE'])
def delete_ticket_route(code):
    table = request.args.get('table', 'tickets')  # Pega o nome da tabela do parâmetro de consulta
    if delete_ticket(code, table):
        return jsonify({'message': 'Ingresso deletado com sucesso'}), 200
    else:
        return jsonify({'error': 'Código não encontrado'}), 404
    
@app.route('/tickets/<code>/validate', methods=['POST'])
def validate_ticket(code):
    if move_ticket_to_validated(code):
        return jsonify({'message': 'Ingresso validado e movido para a tabela de validados'}), 200
    else:
        return jsonify({'error': 'Ingresso não encontrado ou já validado'}), 404
    
import requests  # Adicione esta linha no início do arquivo

@app.route('/process_payment', methods=['POST'])
def process_payment_route():
    """
    Rota Flask para processar pagamentos.
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type deve ser application/json"}), 400

    data = request.json
    print("Dados recebidos:", data)  # Log para debug

    if not data:
        return jsonify({"success": False, "error": "Corpo da requisição vazio"}), 400

    # Validação mais detalhada dos campos
    required_fields = {
        'token': str,
        'paymentMethodId': str,
        'issuerId': str,
        'installments': int,
        'identificationNumber': str,
        'identificationType': str,
        'cardholderEmail': str,
        'transaction_amount': (int, float),
        'user_id': str  # Novo campo para o user_id
    }

    errors = []
    for field, field_type in required_fields.items():
        if field not in data:
            errors.append(f"Campo '{field}' ausente")
        elif not isinstance(data[field], field_type) and not (isinstance(data[field], (int, float)) and field_type in (int, float)):
            errors.append(f"Campo '{field}' deve ser do tipo {field_type.__name__}")

    if errors:
        return jsonify({"success": False, "error": "; ".join(errors)}), 400

    # Preparar os dados para a função process_payment
    try:
        payment_data = {
            "token": data['token'],
            "payment_method_id": data['paymentMethodId'],
            "issuer_id": data['issuerId'],
            "installments": int(data['installments']),
            "transaction_amount": float(data['transaction_amount']),
            "payer": {
                "email": data['cardholderEmail'],
                "identification": {
                    "type": data['identificationType'],
                    "number": data['identificationNumber']
                }
            }
        }
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Erro ao converter dados: {str(e)}"}), 400

    # Chamar a função para processar o pagamento
    payment_response = process_payment(payment_data)

    if payment_response.get("success"):
        if payment_response["status"] == "approved":
            # Após o pagamento ser aprovado, gerar o ingresso e associar ao usuário
            ticket_data = {
                "name": data.get('name'),
                "email": data['cardholderEmail'],
                "cpf": data['identificationNumber'],
                "table": "tickets",
                "user_id": data['user_id'],
                "quantity": data.get('quantity', 1)  # Passando a quantidade de tickets
            }

            # Faz uma requisição HTTP para a rota /generate_ticket
            try:
                response = requests.post(
                    "http://127.0.0.1:3000/generate_ticket",  # URL da rota
                    json=ticket_data,  # Dados do ticket
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 201:
                    return jsonify({
                        "success": True,
                        "status": "approved",
                        "message": "Pagamento aprovado!",
                        "ticket": response.json()
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Erro ao gerar ingresso: {response.json().get('error')}"
                    }), response.status_code
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"Erro ao fazer requisição para /generate_ticket: {str(e)}"
                }), 500

        elif payment_response["status"] == "in_process" or payment_response["status"] == "pending":
            return jsonify({
                "success": True,
                "status": payment_response["status"],
                "message": "Pagamento em processamento.",
                "payment": payment_response["payment"]
            }), 200
    else:
        return jsonify({
            "success": False,
            "status": payment_response.get("status"),
            "error": payment_response.get("error", "Erro ao processar pagamento.")
        }), 400

@app.route('/process_payment_pix', methods=['POST'])
def process_payment_pix_route():
    """
    Rota Flask para processar pagamentos PIX.
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type deve ser application/json"}), 400
    
    data = request.json
    print("Dados recebidos:", data)  # Log para debug
    
    if not data:
        return jsonify({"success": False, "error": "Corpo da requisição vazio"}), 400

    # Validação dos campos obrigatórios
    required_fields = {
        'cardholderEmail': str,
        'identificationNumber': str,
        'identificationType': str,
        'transaction_amount': (int, float)
    }

    errors = []
    for field, field_type in required_fields.items():
        if field not in data:
            errors.append(f"Campo '{field}' ausente")
        elif not isinstance(data[field], field_type) and not (isinstance(data[field], (int, float)) and field_type in (int, float)):
            errors.append(f"Campo '{field}' deve ser do tipo {field_type.__name__}")

    if errors:
        return jsonify({"success": False, "error": "; ".join(errors)}), 400

    # Chamar a função para processar o pagamento PIX
    payment_response = process_payment_pix(data)

    if payment_response.get("success"):
        if payment_response["status"] == "pending":
            return jsonify({
                "success": True,
                "status": "pending",
                "message": "Pagamento PIX gerado com sucesso!",
                "pix_qr_code": payment_response["pix_qr_code"],
                "pix_qr_code_base64": payment_response["pix_qr_code_base64"],
                "pix_copia_cola": payment_response["pix_copia_cola"]  # Incluindo o código PIX copia e cola
            }), 200
    else:
        return jsonify({"success": False, "status": payment_response.get("status"), "error": payment_response.get("error", "Erro ao processar pagamento PIX.")}), 400

@app.route('/lotes', methods=['GET'])
def listar_lotes_route():
    lotes = listar_lotes()
    return jsonify([{
        "id": lote[0],
        "nome": lote[1],
        "descricao": lote[2],
        "valor": lote[3],
        "quantidade": lote[4]
    } for lote in lotes]), 200

@app.route('/lotes', methods=['POST'])
def adicionar_lote_route():
    data = request.json
    nome = data.get('nome')
    descricao = data.get('descricao')
    valor = data.get('valor')
    quantidade = data.get('quantidade')

    if not nome or not valor or not quantidade:
        return jsonify({'error': 'Dados incompletos'}), 400

    id_lote = adicionar_lote(nome, descricao, valor, quantidade)
    return jsonify({'id': id_lote}), 201

@app.route('/lotes/<int:id>', methods=['PUT'])
def editar_lote_route(id):
    data = request.json
    nome = data.get('nome')
    descricao = data.get('descricao')
    valor = data.get('valor')
    quantidade = data.get('quantidade')

    if editar_lote(id, nome, descricao, valor, quantidade):
        return jsonify({'message': 'Lote atualizado com sucesso'}), 200
    else:
        return jsonify({'error': 'Lote não encontrado ou dados não alterados'}), 404

@app.route('/lotes/<int:id>', methods=['DELETE'])
def excluir_lote_route(id):
    if excluir_lote(id):
        return jsonify({'message': 'Lote excluído com sucesso'}), 200
    else:
        return jsonify({'error': 'Lote não encontrado'}), 404
    
@app.route('/user_tickets/<user_id>', methods=['GET'])
def get_user_tickets(user_id):
    table = request.args.get('table', 'tickets')  # Pega o nome da tabela do parâmetro de consulta
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM {table} WHERE user_id = ?', (user_id,))
        tickets = cursor.fetchall()
        return jsonify([{'code': t[0], 'name': t[1], 'email': t[2], 'cpf': t[3]} for t in tickets]), 200
    
@app.route("/check-email", methods=["POST"])
def check_email():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "E-mail é obrigatório."}), 400

    try:
        print(f"Verificando se o e-mail existe: {email}")  # Debug
        response = cognito_service.check_email_exists(email)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify(response), 200
    except Exception as e:
        print(f"Erro ao verificar e-mail: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    if not email or not password or not name:
        return jsonify({"error": "Todos os campos são obrigatórios."}), 400

    try:
        print(f"Registrando usuário: {email}")  # Debug
        response = cognito_service.sign_up(email, password, name)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Usuário registrado com sucesso!", "data": response}), 201
    except Exception as e:
        print(f"Erro ao registrar usuário: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    email = data.get("email")
    code = data.get("code")

    if not email or not code:
        return jsonify({"error": "E-mail e código são obrigatórios."}), 400

    try:
        print(f"Verificando código para o e-mail: {email}")  # Debug
        response = cognito_service.confirm_sign_up(email, code)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "E-mail verificado com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao verificar código: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    print(f"Recebendo requisição de login: {data}")  # Debug

    if not email or not password:
        print("Erro: E-mail e senha são obrigatórios.")  # Debug
        return jsonify({"error": "E-mail e senha são obrigatórios."}), 400

    try:
        print(f"Tentando autenticar o usuário: {email}")  # Debug
        response = cognito_service.login(email, password)
        print(f"Resposta do Cognito: {response}")  # Debug

        # Decodifica o IdToken para obter o user_id
        id_token = response["AuthenticationResult"]["IdToken"]
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        user_id = decoded_token.get("sub")  # O campo 'sub' é o user_id no Cognito

        # Adiciona o user_id à resposta
        response["AuthenticationResult"]["UserId"] = user_id

        return jsonify({
            "message": "Login realizado com sucesso!",
            "data": {
                "AuthenticationResult": response["AuthenticationResult"],
                "user_id": user_id  # Retorna o user_id
            }
        }), 200
    except Exception as e:
        print(f"Erro ao fazer login: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

@app.route("/logout", methods=["POST"])
def logout():
    data = request.json
    access_token = data.get("access_token")

    if not access_token:
        return jsonify({"error": "Token de acesso é obrigatório."}), 400

    try:
        print(f"Fazendo logout para o token: {access_token}")  # Debug
        response = cognito_service.logout(access_token)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Logout realizado com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao fazer logout: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

@app.route("/user", methods=["GET"])
def get_user():
    access_token = request.headers.get("Authorization")

    if not access_token:
        return jsonify({"error": "Token de acesso é obrigatório."}), 400

    # Removendo "Bearer " caso esteja presente
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]

    try:
        print(f"Recuperando informações do usuário para o token: {access_token}")  # Debug
        response = cognito_service.get_user(access_token)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Usuário recuperado com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao recuperar informações do usuário: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=3000)
