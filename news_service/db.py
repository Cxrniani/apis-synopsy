import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

NEWS_DIRETORIO = os.environ['NEWS_DATABASE_PATH']
NEWS_NOME_BANCO = os.environ['NEWS_DATABASE_NAME']

# Cria o caminho completo para o banco de dados de notícias
NEWS_DATABASE = os.path.join(NEWS_DIRETORIO, NEWS_NOME_BANCO)

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
                date TEXT NOT NULL
            )
        ''')
        conn.commit()

def add_news(image, title, subtitle, date):
    with sqlite3.connect(NEWS_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO news (image, title, subtitle, date)
            VALUES (?, ?, ?, ?)
        ''', (image, title, subtitle, date))
        conn.commit()
        return cursor.lastrowid
    
def get_all_news():
    with sqlite3.connect(NEWS_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM news')
        return cursor.fetchall()