from flask import Flask, request, jsonify
from flask_cors import CORS
from services.generate_qrcode_service import generate_qr_code
from services.generate_code_service import generate_code
from utils.db import *
from services.process_payment import process_payment

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
    data = request.json

    # Validação de campos obrigatórios
    required_fields = [
        'token', 'paymentMethodId', 'issuerId', 'installments',
        'identificationNumber', 'identificationType', 'cardholderEmail', 'transaction_amount'
    ]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"success": False, "error": f"Campo '{field}' ausente ou inválido"}), 400

    # Preparar os dados para a função process_payment
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

    # Chamar a função separada para processar o pagamento
    try:
        payment_response = process_payment(payment_data)

        if payment_response["success"]:
            return jsonify({"success": True, "payment": payment_response["payment"]}), 201
        else:
            return jsonify({
                "success": False,
                "error": payment_response.get("error", "Erro ao processar pagamento"),
                "details": payment_response.get("response", {})
            }), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
