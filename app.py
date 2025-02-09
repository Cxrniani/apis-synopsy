import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import base64
from ticket_service.services.generate_qrcode_service import generate_qr_code
from ticket_service.services.generate_code_service import generate_code
from ticket_service.utils.db import *
from ticket_service.services.process_payment import *
import requests
from auth_service.services.cognito_service import *
import jwt
from news_service.db import init_news_db, add_news, get_all_news, get_news_by_id, upload_image_to_s3,upload_base64_to_s3
from werkzeug.utils import secure_filename
import uuid
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup

load_dotenv()
AWS_REGION = os.environ['AWS_REGION']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
s3_client = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
)

cognito_service = CognitoService()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
init_news_db()
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 5MB

@app.route('/api/upload', methods=['POST'])
def handle_file_upload():
    print("\n=== Novo upload de imagem do editor ===")
    print("Headers:", request.headers)
    print("Form data:", request.form)
    print("Files:", request.files)
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
        
    file = request.files['file']
    print(f"Arquivo recebido: {file.filename}, tipo: {file.content_type}")
    if file.filename == '':
        return jsonify({"error": "Nome de arquivo inválido"}), 400

    try:
        # Gera nome único para o arquivo com caminho específico
        filename = f"editor/{uuid.uuid4()}-{secure_filename(file.filename)}"
        image_url = upload_image_to_s3(file, filename)
        
        return jsonify({"url": image_url}), 200
    except Exception as e:
        print(f"Erro no upload: {str(e)}")
        return jsonify({"error": "Erro ao processar imagem"}), 500

@app.route('/news/create', methods=['POST'])
def create_news():
    try:
        # Validação básica
        if 'coverImage' not in request.files or 'content' not in request.form:
            return jsonify({"error": "Campos obrigatórios: coverImage e content"}), 400

        cover_image = request.files['coverImage']
        content = request.form['content']

        # Upload capa
        cover_filename = f"covers/{uuid.uuid4()}-{secure_filename(cover_image.filename)}"
        cover_url = upload_image_to_s3(cover_image, cover_filename)

        # Processar conteúdo
        processed_content = process_quill_images(content)
        title, subtitle, clean_content = parse_html_content(processed_content)

        # Adicionar ao banco
        news_id = add_news(
            cover_url,
            title,
            subtitle,
            clean_content,
            datetime.now().isoformat()
        )

        return jsonify({
            "id": news_id,
            "cover_url": cover_url,
            "title": title,
            "subtitle": subtitle
        }), 201

    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({"error": str(e)}), 500

def process_quill_images(html_content):
    """Substitui TODAS as imagens (base64 e URLs) por S3"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src', '')
        
        # Se for base64
        if src.startswith('data:image'):
            try:
                # Extrai tipo e dados da string base64
                match = re.match(r'data:image/(?P<ext>\w+);base64,(?P<data>.+)', src)
                if match:
                    ext = match.group('ext')
                    data = match.group('data')
                    
                    # Upload para S3
                    image_url = upload_base64_to_s3(data, ext)
                    img_tag['src'] = image_url
                else:
                    img_tag.decompose()
                    
            except Exception as e:
                print(f"Erro processando imagem: {str(e)}")
                img_tag.decompose()
    
    return str(soup)

def parse_html_content(html):
    """Extrai E REMOVE h1/h2 do conteúdo"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extrai e remove h1
    h1_tag = soup.find('h1')
    title = h1_tag.get_text(strip=True) if h1_tag else 'Sem título'
    if h1_tag:
        h1_tag.decompose()
    
    # Extrai e remove h2
    h2_tag = soup.find('h2')
    subtitle = h2_tag.get_text(strip=True) if h2_tag else 'Sem subtítulo'
    if h2_tag:
        h2_tag.decompose()
    
    return title, subtitle, str(soup)  # ← conteúdo SEM h1/h2

@app.route('/news', methods=['GET'])
def get_all_news_route():
    news = get_all_news()
    return jsonify([{
        'id': n[0],
        'image': n[1],
        'title': n[2],
        'subtitle': n[3],
        'content': n[4],  # Corrigido: conteúdo é a 4ª coluna
        'date': n[5]      # Corrigido: data é a 5ª coluna
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
            'content': news[4],  # Corrigido
            'date': news[5]      # Corrigido
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
    quantity = data.get('quantity', 1)  # Quantidade de tickets a serem gerados

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
