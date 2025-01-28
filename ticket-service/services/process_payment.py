import mercadopago
import os
from dotenv import load_dotenv
import uuid

# Carrega as variáveis de ambiente
load_dotenv()

# Configura o SDK do Mercado Pago
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
if not MP_ACCESS_TOKEN:
    raise ValueError("MP_ACCESS_TOKEN não está configurado.")
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

def process_payment(payment_data):
    """
    Processa um pagamento com os dados fornecidos.
    
    :param payment_data: Um dicionário com os dados necessários para o pagamento.
    :return: O resultado do pagamento ou uma mensagem de erro.
    """
    try:
        # Configura a chave de idempotência
        request_options = mercadopago.config.RequestOptions()
        request_options.custom_headers = {
            "x-idempotency-key": str(uuid.uuid4())
        }

        # Cria o pagamento
        payment_response = sdk.payment().create(payment_data, request_options)

        # Verifica a resposta do pagamento
        if payment_response.get("status") == 201:
            return {"success": True, "payment": payment_response["response"]}
        else:
            return {
                "success": False,
                "error": payment_response.get("message", payment_response),
                "response": payment_response
            }

    except Exception as e:
        # Tratamento de erros
        return {"success": False, "error": str(e)}
