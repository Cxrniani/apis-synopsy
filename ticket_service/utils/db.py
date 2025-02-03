import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DIRETORIO = os.environ['DATABASE_PATH']  
NOME_BANCO = os.environ['DATABASE_NAME']  

# Cria o caminho completo para o banco de dados
DATABASE = os.path.join(DIRETORIO, NOME_BANCO)

def init_db(table='tickets'):
    os.makedirs(DIRETORIO, exist_ok=True)
    
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                cpf TEXT NOT NULL,
                qr_code_path TEXT,
                user_id TEXT  -- Adicionando o user_id para associar o ingresso ao usuário
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                valor REAL NOT NULL,
                quantidade INTEGER NOT NULL
            )
        ''')
        conn.commit()

def store_ticket(code, name, email, cpf, user_id, table='tickets'):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f'INSERT INTO {table} (code, name, email, cpf, user_id) VALUES (?, ?, ?, ?, ?)',
                           (code, name, email, cpf, user_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Código já existe

        
def get_ticket(code, table):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM {table} WHERE code = ?', (code,))
        return cursor.fetchone()  # Retorna uma única linha

def get_all_tickets(table):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM {table}')
        return cursor.fetchall()  # Retorna todas as linhas

def update_ticket(code, table, name=None, email=None, cpf=None):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        
        if cpf is not None:
            updates.append("cpf = ?")
            params.append(cpf)

        if updates:
            params.append(code)
            query = f'UPDATE {table} SET {", ".join(updates)} WHERE code = ?'
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0  # Retorna True se alguma linha foi atualizada

    return False  # Retorna False se não houver atualizações

def delete_ticket(code, table='tickets'):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # Primeiro, recupera o caminho do QR Code associado ao ingresso
        cursor.execute(f'SELECT qr_code_path FROM {table} WHERE code = ?', (code,))
        result = cursor.fetchone()
        
        if result:
            qr_code_path = result[0]  # Obtém o caminho do QR Code
            
            # Deleta o ingresso do banco de dados
            cursor.execute(f'DELETE FROM {table} WHERE code = ?', (code,))
            conn.commit()

            # Remove o arquivo de imagem do QR Code, se existir
            if os.path.exists(qr_code_path):
                os.remove(qr_code_path)
                
            return True  # Retorna True se uma linha foi deletada
        else:
            return False  # Retorna False se o código não foi encontrado

def move_ticket_to_validated(code, table='tickets'):
    # Nome da tabela de destino
    validated_table = 'validated_tickets'
    
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # Recupera os dados do ingresso da tabela original
        cursor.execute(f'SELECT * FROM {table} WHERE code = ?', (code,))
        ticket = cursor.fetchone()

        if ticket:
            # Insere os dados do ingresso na tabela 'validated_tickets'
            cursor.execute(f'''
                INSERT INTO {validated_table} (code, name, email, cpf, qr_code_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (ticket[0], ticket[1], ticket[2], ticket[3], ticket[4]))
            
            # Deleta o ingresso da tabela original
            cursor.execute(f'DELETE FROM {table} WHERE code = ?', (code,))
            conn.commit()
            
            return True  # Retorna True se a operação for bem-sucedida
        else:
            return False  # Retorna False se o ingresso não for encontrado
        
def adicionar_lote(nome, descricao, valor, quantidade):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lotes (nome, descricao, valor, quantidade)
            VALUES (?, ?, ?, ?)
        ''', (nome, descricao, valor, quantidade))
        conn.commit()
        return cursor.lastrowid  # Retorna o ID do lote adicionado

def listar_lotes():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM lotes')
        return cursor.fetchall()  # Retorna todos os lotes

def editar_lote(id, nome=None, descricao=None, valor=None, quantidade=None):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        updates = []
        params = []

        if nome is not None:
            updates.append("nome = ?")
            params.append(nome)
        if descricao is not None:
            updates.append("descricao = ?")
            params.append(descricao)
        if valor is not None:
            updates.append("valor = ?")
            params.append(valor)
        if quantidade is not None:
            updates.append("quantidade = ?")
            params.append(quantidade)

        if updates:
            params.append(id)
            query = f'UPDATE lotes SET {", ".join(updates)} WHERE id = ?'
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0  # Retorna True se alguma linha foi atualizada

    return False  # Retorna False se não houver atualizações

def excluir_lote(id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM lotes WHERE id = ?', (id,))
        conn.commit()
        return cursor.rowcount > 0  # Retorna True se uma linha foi deletada
