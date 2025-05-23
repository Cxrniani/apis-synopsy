import mercadopago
import os
from dotenv import load_dotenv
import uuid
import hashlib
import hmac

# Carrega as variáveis de ambiente
load_dotenv()

# Configura o SDK do Mercado Pago
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
MP_CLIENT_ID = os.environ.get("MP_CLIENT_ID")
if not MP_ACCESS_TOKEN:
    raise ValueError("MP_ACCESS_TOKEN não está configurado.")
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

def process_payment(payment_data):
    try:
        request_options = mercadopago.config.RequestOptions()
        request_options.custom_headers = {
            "x-idempotency-key": str(uuid.uuid4()),
        }


        print("Enviando dados para o Mercado Pago:", payment_data)  # Log dos dados enviados
        payment_response = sdk.payment().create(payment_data, request_options)

        print("Resposta bruta do Mercado Pago:", payment_response)  # Log da resposta completa

        if payment_response.get("status") == 201:
            payment = payment_response["response"]
            status = payment["status"]

            if status == "approved":
                return {"success": True, "status": "approved", "payment": payment}
            elif status in ["in_process", "pending"]:
                return {"success": True, "status": "in_process", "payment": payment}
            else:
                error_message = f"Pagamento não aprovado. Status: {status}, Detalhes: {payment.get('status_detail')}"
                return {"success": False, "status": "rejected", "error": error_message, "details": payment}
        else:
            error_message = payment_response.get("message", "Erro ao processar pagamento.")
            return {
                "success": False,
                "status": "error",
                "error": error_message,
                "details": payment_response  # Log adicional do erro
            }

    except Exception as e:
        return {"success": False, "status": "error", "error": str(e)}
    
def get_payment_details(payment_id):
    try:
        # Usa o SDK do Mercado Pago para buscar os detalhes do pagamento
        payment_response = sdk.payment().get(payment_id)
        print("Resposta da API do Mercado Pago:", payment_response)  # Log para debug

        # Verifica se a resposta foi bem-sucedida
        if payment_response.get("status") == 200:
            return payment_response["response"]
        else:
            raise Exception(f"Erro ao buscar detalhes do pagamento: {payment_response.get('message')}")
    except Exception as e:
        raise Exception(f"Erro ao buscar detalhes do pagamento: {str(e)}")
    
    
def process_payment_pix(payment_data):
    """
    Processa um pagamento PIX com os dados fornecidos.
    
    :param payment_data: Um dicionário com os dados necessários para o pagamento PIX.
    :return: O resultado do pagamento ou uma mensagem de erro.
    """
    try:
        # Configura a chave de idempotência
        request_options = mercadopago.config.RequestOptions()
        request_options.custom_headers = {
            "x-idempotency-key": str(uuid.uuid4())
        }

        # Cria a cobrança PIX
        payment_response = sdk.payment().create({
            "transaction_amount": float(payment_data["transaction_amount"]),
            "payment_method_id": "pix",
            "payer": {
                "email": payment_data["payer"]["email"],
                "first_name": payment_data["payer"]["first_name"],
                "last_name": payment_data["payer"]["last_name"],
                "identification": {
                    "type": payment_data["payer"]["identification"]["type"],
                    "number": payment_data["payer"]["identification"]["number"]
                }
            },
            "external_reference": payment_data["external_reference"]  # Referência externa
        }, request_options)
        print(payment_response)  # Log para depuração

        # Verifica a resposta do pagamento
        if payment_response.get("status") == 201:
            payment = payment_response["response"]
            status = payment["status"]

            # Log da resposta completa para depuração
            print("Resposta completa do Mercado Pago:", payment)

            # Tratamento dos status
            if status == "pending":
                return {
                    "success": True,
                    "status": "pending",
                    "payment": payment,
                    "pix_qr_code": payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code"),
                    "pix_qr_code_base64": payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code_base64"),
                    "pix_copia_cola": payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code")  # Código PIX copia e cola
                }
            else:
                # Status rejeitado ou outros casos
                error_message = f"Pagamento não aprovado. Status: {status}, Detalhes: {payment.get('status_detail')}"
                return {"success": False, "status": "rejected", "error": error_message, "details": payment}
        else:
            # Erros na requisição à API
            error_message = payment_response.get("message", "Erro ao processar pagamento.")
            return {"success": False, "status": "error", "error": error_message}

    except Exception as e:
        # Tratamento de erros gerais
        return {"success": False, "status": "error", "error": str(e)}