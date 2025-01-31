from flask import Flask, request, jsonify
from flask_cors import CORS
from services.generate_qrcode_service import generate_qr_code
from services.generate_code_service import generate_code
from utils.db import *
from services.process_payment import *

app = Flask(__name__)
CORS(app)  # Habilita CORS para permitir requisições de outros domínios

@app.route('/generate_ticket', methods=['POST'])
def generate_ticket():
    data = request.json
    
    name = data.get('name')
    email = data.get('email')
    cpf = data.get('cpf')
    table = data.get('table')

    if not name or not email or not cpf or not table:
        return jsonify({'error': 'Dados incompletos'}), 400

    code = generate_code()
    init_db(table)

    # Gera o QR Code e obtém o caminho da imagem gerada
    qr_code_path = generate_qr_code(code)  # Gera o QR Code

    if store_ticket(code, name, email, cpf, qr_code_path, table):
        return jsonify({'code': code, 'qr_code_path': qr_code_path}), 201  # Retorna o código e caminho do QR Code gerado
    else:
        return jsonify({'error': 'Código já existente'}), 409


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
            return jsonify({"success": True, "status": "approved", "message": "Pagamento aprovado!", "payment": payment_response["payment"]}), 200
        elif payment_response["status"] == "in_process" or payment_response["status"] == "pending":
            return jsonify({"success": True, "status": payment_response["status"], "message": "Pagamento em processamento.", "payment": payment_response["payment"]}), 200
    else:
        return jsonify({"success": False, "status": payment_response.get("status"), "error": payment_response.get("error", "Erro ao processar pagamento.")}), 400

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

if __name__ == '__main__':
    app.run(debug=True)
