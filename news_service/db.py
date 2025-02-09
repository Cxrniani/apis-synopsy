import sqlite3
import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from datetime import datetime
import base64
import uuid

load_dotenv()


NEWS_DIRETORIO = os.environ['NEWS_DATABASE_PATH']
NEWS_NOME_BANCO = os.environ['NEWS_DATABASE_NAME']

# Cria o caminho completo para o banco de dados de notícias
NEWS_DATABASE = os.path.join(NEWS_DIRETORIO, NEWS_NOME_BANCO)

# Configurações do S3
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
AWS_REGION = os.environ['AWS_REGION']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']

# Inicializa o cliente do S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)
def init_news_db():
    os.makedirs(NEWS_DIRETORIO, exist_ok=True)
    
    with sqlite3.connect(NEWS_DATABASE) as conn:
        cursor = conn.cursor()

        cursor.execute(''' 
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT NOT NULL,
                content TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        conn.commit()

def upload_image_to_s3(file, filename):
    """Upload de arquivo binário para o S3"""
    try:
        s3_client.upload_fileobj(
            file,
            S3_BUCKET_NAME,
            filename,
            ExtraArgs={
                'ContentType': file.content_type
            }
        )
        return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    except ClientError as e:
        raise Exception(f"Erro S3: {e}")

def upload_base64_to_s3(base64_data, ext):
    """Faz upload de imagens base64 para o S3"""
    try:
        # Gera nome único com a extensão correta
        filename = f"editor/{uuid.uuid4()}.{ext}"
        # Decodifica os dados
        image_data = base64.b64decode(base64_data)
        
        # Faz upload
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=filename,
            Body=image_data,
            ContentType=f"image/{ext}"
        )
        
        return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    except Exception as e:
        raise Exception(f"Erro ao processar base64: {str(e)}")

def add_news(image_url, title, subtitle, content, date):
    """Adiciona notícia com URL da imagem já processada"""
    with sqlite3.connect(NEWS_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO news (image, title, subtitle, content, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (image_url, title, subtitle, content, date))
        conn.commit()
        return cursor.lastrowid
    
def get_all_news():
    with sqlite3.connect(NEWS_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM news')
        return cursor.fetchall()
    
def get_news_by_id(news_id):
    with sqlite3.connect(NEWS_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM news WHERE id = ?', (news_id,))
        return cursor.fetchone()
