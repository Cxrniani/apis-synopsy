import qrcode
import os
from dotenv import load_dotenv

load_dotenv()

DIRETORIO = os.environ['ASSETS_PATH']

def generate_qr_code(ticket_code, output_dir=DIRETORIO):
    os.makedirs(output_dir, exist_ok=True)
    
    qr_code_file = os.path.join(output_dir, f'{ticket_code}.png')

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    qr.add_data(ticket_code)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_code_file)

    return qr_code_file  # Retorna o caminho do arquivo gerado

