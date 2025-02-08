import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from ticket_service.utils.db import *
from ticket_service.services.process_payment import *
from ticket_service.services.generate_code_service import generate_code
import requests
from auth_service.services.cognito_service import *
import jwt
from news_service.db import init_news_db, add_news, get_all_news
from decimal import Decimal
cognito_service = CognitoService()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
init_news_db()

# Função para validar imagens Base64
def is_base64(string: str) -> bool:
    base64_pattern = re.compile(r"^data:image\/(png|jpg|jpeg);base64,")
    return bool(base64_pattern.match(string))

@app.route('/news/create', methods=['POST'])
def create_news():
    data = request.json
    image = data.get('image')
    title = data.get('title')
    subtitle = data.get('subtitle')
    date = data.get('date')
    content = data.get('content')  # Novo campo

    if not all([image, title, subtitle, date, content]):  # Verifique se todos os campos obrigatórios estão presentes
        return jsonify({"error": "Todos os campos são obrigatórios."}), 400

    # Verificar se a imagem está em Base64
    if not is_base64(image):
        return jsonify({"error": "Formato de imagem inválido. A imagem deve estar em Base64."}), 400

    try:
        # Adicionando log para verificar o que está sendo enviado
        print("Dados recebidos:", data)

        news_id = add_news(image, title, subtitle, date, content)  # Passando content
        return jsonify({"message": "Notícia adicionada com sucesso!", "news_id": news_id}), 201
    except Exception as e:
        print("Erro ao adicionar notícia:", str(e))  # Log do erro
        return jsonify({"error": str(e)}), 500

@app.route('/news', methods=['GET'])
def get_all_news_route():
    news = get_all_news()
    return jsonify([{
        'id': n[0],
        'image': n[1],
        'title': n[2],
        'subtitle': n[3],
        'date': n[4],
        'content': n[5]  # Incluindo o conteúdo da notícia
    } for n in news]), 200

@app.route('/news/<int:news_id>', methods=['GET'])
def get_news(news_id):
    news = get_news_by_id(news_id)
    if news:
        return jsonify({
            'id': news[0],
            'image': news[1],
            'title': news[2],
            'subtitle': news[3],
            'date': news[4],
            'content': news[5]  # Incluindo o conteúdo da notícia
        }), 200
    else:
        return jsonify({"error": "Notícia não encontrada"}), 404
    
@app.route('/generate_ticket', methods=['POST'])
def generate_ticket():
    data = request.json
    event_id = data.get('event_id')
    name = data.get('name')
    email = data.get('email')
    cpf = data.get('cpf')
    table = data.get('table')
    user_id = data.get('user_id')
    quantity = data.get('quantity', 1)
    price = float(data.get('price'))
    lot = data.get('lot')

    if not all([event_id, name, email, cpf, user_id, lot]) or price is None:
        return jsonify({'error': 'Dados incompletos'}), 400

    tickets = []
    for _ in range(quantity):
        code = generate_code()
        if store_ticket(event_id, code, name, email, cpf, user_id, Decimal(str(price)), lot):
            tickets.append({'code': code})
            # Atualiza o saldo do administrador
            update_admin_balance('7b87fd15-bea4-4fff-9033-9224fc0c8a01', price)  # Substitua 'admin_id' pelo ID real do administrador
        else:
            return jsonify({'error': 'Código já existente'}), 409

    return jsonify({'tickets': tickets}), 201


@app.route('/tickets/<event_id>/<code>', methods=['GET'])
def read_ticket(event_id, code):
    ticket = get_ticket(event_id, code)
    if ticket:
        return jsonify(ticket), 200
    else:
        return jsonify({'error': 'Ingresso não encontrado'}), 404

@app.route('/tickets/<event_id>', methods=['GET'])
def read_all_tickets(event_id):
    tickets = get_all_tickets(event_id)
    return jsonify(tickets), 200

@app.route('/tickets/<event_id>/<code>', methods=['PUT'])
def update_ticket_route(event_id, code):
    data = request.json
    name = data.get('name')
    email = data.get('email')
    cpf = data.get('cpf')

    if update_ticket(event_id, code, name, email, cpf):
        return jsonify({'message': 'Ingresso atualizado com sucesso'}), 200
    else:
        return jsonify({'error': 'Código não encontrado ou dados não alterados'}), 404

@app.route('/tickets/<event_id>/<code>', methods=['DELETE'])
def delete_ticket_route(event_id, code):
    if delete_ticket(event_id, code):
        return jsonify({'message': 'Ingresso deletado com sucesso'}), 200
    else:
        return jsonify({'error': 'Código não encontrado'}), 404
    
@app.route('/tickets/<event_id>/<code>/validate', methods=['POST'])
def validate_ticket(event_id, code):
    if move_ticket_to_validated(event_id, code):
        return jsonify({'message': 'Ingresso validado e movido para a tabela de validados'}), 200
    else:
        return jsonify({'error': 'Ingresso não encontrado'}), 404
    

@app.route('/webhook', methods=['POST'])
def webhook():
    # Verifica se a requisição é JSON
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type deve ser application/json"}), 400

    data = request.json
    print("Dados recebidos do webhook:", data)  # Log para debug

    # Verifica se o campo 'data' e 'id' estão presentes
    if 'data' not in data or 'id' not in data['data']:
        return jsonify({"success": False, "error": "Dados inválidos no webhook"}), 400

    # Obtém o ID do pagamento
    payment_id = data['data']['id']

    try:
        # Busca os detalhes do pagamento usando o SDK do Mercado Pago
        payment_details = get_payment_details(payment_id)
        print(type(payment_details))  # ADICIONE ESTE PRINT
        print("Detalhes do pagamento:", payment_details)  # Log para debug

        external_reference = payment_details.get("external_reference")
        print(f'external_reference: {external_reference}')  # ADICIONE ESTE PRINT
        if not external_reference:
            return jsonify({"success": False, "error": "external_reference não encontrado"}), 40
        
        custom_data = json.loads(external_reference)

        # Processa o status do pagamento
        status = payment_details.get("status")
        if status == "approved":
            # Pagamento aprovado, gere o ingresso ou realize outras ações
            print("Pagamento aprovado! Gerando ingresso...")
            ticket_data = {
            "name": custom_data['name'],
            "email": payment_details["payer"]["email"],
            "cpf": payment_details["payer"]["identification"]["number"],
            "table": "tickets",
            "user_id": custom_data["user_id"],
            "quantity": custom_data['quantity'],  # Ajuste conforme necessário
            "price": custom_data["price"],
            "lot": custom_data["lot"],
            "event_id": custom_data["event_id"]
            }
            print("Dados do ticket:", ticket_data)

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
        elif status in ["in_process", "pending"]:
            # Pagamento em processamento
            print("Pagamento em processamento...")
        else:
            # Pagamento rejeitado ou com erro
            print(f"Pagamento não aprovado. Status: {status}")

        return jsonify({"success": True}), 200

    except Exception as e:
        print("Erro ao processar webhook:", str(e))  # Log para debug
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/process_payment', methods=['POST'])
def process_payment_route():
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
        'user_id': str,
        'price': (int, float),
        'lot': str,
        'address': dict  # Novo campo para o endereço
    }

    errors = []
    for field, field_type in required_fields.items():
        if field not in data:
            errors.append(f"Campo '{field}' ausente")
        elif not isinstance(data[field], field_type if isinstance(field_type, tuple) else (field_type,)):
            errors.append(f"Campo '{field}' deve ser do tipo {field_type if isinstance(field_type, tuple) else field_type.__name__}")

    if errors:
        print("Erros de validação:", errors)  # Log para debug
        return jsonify({"success": False, "error": "; ".join(errors)}), 400

    # Preparar os dados para a função process_payment
    try:
        external_reference = json.dumps({
            "lot": data['lot'],
            "price": data['price'],
            "event_id": data['event_id'],
            "user_id": data['user_id'],
            "name": data['name'],
            "quantity": data['quantity']
        })

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
                },
                "address": {
                    "street_name": data['address']['streetName'],
                    "street_number": data['address']['streetNumber'],
                    "zip_code": data['address']['zipCode'],
                    "city": data['address']['city'],
                    "federal_unit": data['address']['state']
                }
            },
            "external_reference": external_reference
        }
        print("Iniciando o processamento de pagamento com os dados:", payment_data)
    except (ValueError, TypeError) as e:
        return jsonify({"success": False, "error": f"Erro ao converter dados: {str(e)}"}), 400

    # Chamar a função para processar o pagamento
    payment_response = process_payment(payment_data)
    print("Resposta do process_payment:", payment_response)  # ADICIONE ESTE PRINT

    if payment_response["status"] == "approved":
        return jsonify({
            "success": True,
            "status": "approved",
            "message": "Pagamento aprovado!",
            "payment": payment_response["payment"]
        }), 200

    if payment_response["status"] == "in_process" or payment_response["status"] == "pending":
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
        'transaction_amount': (int, float),
        'user_id': str,
        'price': (int, float),  # Novo campo para o preço
        'lot': str,              # Novo campo para o lote
        'quantity': int
    }

    errors = []
    for field, field_type in required_fields.items():
        if field not in data:
            errors.append(f"Campo '{field}' ausente")
        elif not isinstance(data[field], field_type) and not (isinstance(data[field], (int, float)) and field_type in (int, float)):
            errors.append(f"Campo '{field}' deve ser do tipo {field_type.__name__}")

    if errors:
        return jsonify({"success": False, "error": "; ".join(errors)}), 400

    external_reference = json.dumps({
        "lot": data['lot'],
        "price": data['price'],
        "event_id": data['event_id'],
        "user_id": data['user_id'],
        "name": data['name'],
        "quantity": data['quantity']
    })
    
    payment_data = {
        "transaction_amount": float(data['transaction_amount']),
        "payer": {
            "email": data['cardholderEmail'],
            "first_name": data["firstName"],       # Acesso direto
            "last_name": data["lastName"],         # Acesso direto
            "identification": {
                "type": data['identificationType'],
                "number": data['identificationNumber']
            }
        },
        "application_fee": data["application_fee"],
        "external_reference": external_reference
}

    # Chamar a função para processar o pagamento PIX
    payment_response = process_payment_pix(payment_data)

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
        return jsonify({"success": False, "status": payment_response.get("status"), "error": 
                        payment_response.get("error", "Erro ao processar pagamento PIX.")}), 400

@app.route('/lotes', methods=['GET'])
def listar_lotes_route():
    lotes = listar_lotes()
    return jsonify(lotes), 200

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
def get_user_tickets_route(user_id):
    event_id = request.args.get('event_id')  # Filtro opcional por evento
    tickets = get_user_tickets(user_id, event_id)
    return jsonify(tickets), 200

    
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
    birthdate = data.get("birthdate")
    gender = data.get("gender")
    phone_number = data.get("phone_number")

    if not email or not password or not name or not birthdate or not gender or not phone_number:
        return jsonify({"error": "Todos os campos são obrigatórios."}), 400

    try:
        print(f"Registrando usuário: {email}")  # Debug
        response = cognito_service.sign_up(email, password, name, birthdate, gender, phone_number)
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
@app.route("/resend-code", methods=["POST"])
def resend_code():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "E-mail é obrigatório."}), 400

    try:
        print(f"Reenviando código de confirmação para: {email}")  # Debug
        response = cognito_service.resend_confirmation_code(email)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Código de confirmação reenviado com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao reenviar código de confirmação: {str(e)}")  # Debug
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

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "E-mail é obrigatório."}), 400

    try:
        print(f"Solicitando redefinição de senha para: {email}")  # Debug
        response = cognito_service.forgot_password(email)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Código de redefinição de senha enviado com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao solicitar redefinição de senha: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400

@app.route("/confirm-forgot-password", methods=["POST"])
def confirm_forgot_password():
    data = request.json
    email = data.get("email")
    code = data.get("code")
    new_password = data.get("new_password")

    if not email or not code or not new_password:
        return jsonify({"error": "E-mail, código e nova senha são obrigatórios."}), 400

    try:
        print(f"Confirmando redefinição de senha para: {email}")  # Debug
        response = cognito_service.confirm_forgot_password(email, code, new_password)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Senha redefinida com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao confirmar redefinição de senha: {str(e)}")  # Debug
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
    
@app.route('/get_user_id_by_email', methods=['POST'])
def get_user_id_by_email():
    """
    Rota para buscar o ID do usuário no Amazon Cognito com base no email.
    
    Espera um JSON no corpo da requisição com o campo 'email'.
    Retorna o ID do usuário ou uma mensagem de erro.
    """
    data = request.json

    # Verifica se o email foi fornecido
    if not data or 'email' not in data:
        return jsonify({"status": "error", "message": "Email não fornecido"}), 400

    email = data['email']

    # Busca o usuário pelo email
    result = cognito_service.get_user_by_email(email)

    if result["status"] == "success":
        # Retorna o ID do usuário (username no Cognito)
        user_id = result["user"]["username"]
        return jsonify({"status": "success", "user_id": user_id}), 200
    else:
        # Retorna a mensagem de erro
        return jsonify({"status": "error", "message": result["message"]}), 404
@app.route("/update_user", methods=["POST"])
def update_user():
    data = request.json
    access_token = request.headers.get("Authorization")

    if not access_token:
        return jsonify({"error": "Token de acesso é obrigatório."}), 400

    # Removendo "Bearer " caso esteja presente
    if access_token.startswith("Bearer "):
        access_token = access_token[7:]

    try:
        print(f"Atualizando informações do usuário para o token: {access_token}")  # Debug
        response = cognito_service.update_user(access_token, data)
        print(f"Resposta do Cognito: {response}")  # Debug
        return jsonify({"message": "Usuário atualizado com sucesso!", "data": response}), 200
    except Exception as e:
        print(f"Erro ao atualizar informações do usuário: {str(e)}")  # Debug
        return jsonify({"error": str(e)}), 400
    
@app.route('/admin/balance', methods=['GET'])
def get_balance():
    admin_id = '7b87fd15-bea4-4fff-9033-9224fc0c8a01'  # Substitua pelo ID real do administrador
    balance = get_admin_balance(admin_id)
    return jsonify({'balance': float(balance)}), 200

@app.route('/admin/withdraw', methods=['POST'])
def withdraw():
    admin_id = '7b87fd15-bea4-4fff-9033-9224fc0c8a01'  # Substitua pelo ID real do administrador
    data = request.json
    amount = data.get('amount')

    if amount is None:
        return jsonify({'error': 'Amount is required'}), 400

    balance = get_admin_balance(admin_id)
    if balance < Decimal(str(amount)):
        return jsonify({'error': 'Saldo insuficiente'}), 400

    if add_withdrawal_request(admin_id, amount):
        update_admin_balance(admin_id, -Decimal(str(amount)))
        return jsonify({'message': 'Solicitação de saque enviada'}), 200
    else:
        return jsonify({'error': 'Erro ao processar saque'}), 500

@app.route('/admin/withdrawals', methods=['GET'])
def get_withdrawals():
    admin_id = '7b87fd15-bea4-4fff-9033-9224fc0c8a01'  # Substitua pelo ID real do administrador
    table = dynamodb.Table('admin_balance')
    response = table.get_item(Key={'admin_id': admin_id})
    if 'Item' in response:
        withdrawals = response['Item'].get('withdrawal_requests', [])
        return jsonify({'withdrawals': withdrawals}), 200
    return jsonify({'withdrawals': []}), 200

@app.route('/admin/mark_withdrawal_done', methods=['POST'])
def mark_withdrawal_done():
    admin_id = '7b87fd15-bea4-4fff-9033-9224fc0c8a01'  # Substitua pelo ID real do administrador
    data = request.json
    index = data.get('index')

    if index is None:
        return jsonify({'error': 'Index is required'}), 400

    if mark_withdrawal_as_done(admin_id, index):
        return jsonify({'message': 'Saque marcado como realizado'}), 200
    else:
        return jsonify({'error': 'Erro ao marcar saque como realizado'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=3000)
