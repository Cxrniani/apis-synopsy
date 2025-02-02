import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DIRETORIO = os.environ['DATABASE_PATH']
NOME_BANCO = os.environ['DATABASE_NAME']

# Cria o caminho completo para o banco de dados
DATABASE = os.path.join(DIRETORIO, NOME_BANCO)

def init_db():
    os.makedirs(DIRETORIO, exist_ok=True)
    
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                subtitle TEXT,
                image TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def store_news(title, subtitle, image, content):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO news (title, subtitle, image, content)
            VALUES (?, ?, ?, ?)
        ''', (title, subtitle, image, content))
        conn.commit()
        return cursor.lastrowid

def get_news(id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM news WHERE id = ?', (id,))
        return cursor.fetchone()

def get_all_news():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM news')
        return cursor.fetchall()

def update_news(id, title=None, subtitle=None, image=None, content=None):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if subtitle is not None:
            updates.append("subtitle = ?")
            params.append(subtitle)
        if image is not None:
            updates.append("image = ?")
            params.append(image)
        if content is not None:
            updates.append("content = ?")
            params.append(content)

        if updates:
            params.append(id)
            query = f'UPDATE news SET {", ".join(updates)} WHERE id = ?'
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    return False

def delete_news(id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM news WHERE id = ?', (id,))
        conn.commit()
        return cursor.rowcount > 0