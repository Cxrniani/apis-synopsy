import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

# Configurações do banco de dados MySQL
DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_NAME = os.environ['DB_NAME']

def get_db_connection():
    """Retorna uma conexão com o banco de dados MySQL."""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=3306
    )

def init_db(table='tickets'):
    """Inicializa o banco de dados e cria as tabelas se não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Cria a tabela de tickets
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {table} (
            code VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            cpf VARCHAR(14) NOT NULL,
            user_id VARCHAR(255),
            price FLOAT,  -- Novo campo para o preço
            lot VARCHAR(255)  -- Novo campo para o lote
        )
    ''')

    # Cria a tabela de lotes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lotes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            descricao TEXT,
            valor FLOAT NOT NULL,
            quantidade INT NOT NULL
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()

def store_ticket(code, name, email, cpf, user_id, price, lot, table='tickets'):
    """Armazena um ticket no banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f'''
            INSERT INTO {table} (code, name, email, cpf, user_id, price, lot)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (code, name, email, cpf, user_id, price, lot))
        conn.commit()
        return True
    except mysql.connector.IntegrityError:
        return False  # Código já existe
    finally:
        cursor.close()
        conn.close()

def get_ticket(code, table):
    """Recupera um ticket pelo código."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM {table} WHERE code = %s', (code,))
    ticket = cursor.fetchone()  # Retorna uma única linha
    cursor.close()
    conn.close()
    return ticket

def get_all_tickets(table):
    """Recupera todos os tickets."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM {table}')
    tickets = cursor.fetchall()  # Retorna todas as linhas
    cursor.close()
    conn.close()
    return tickets

def update_ticket(code, table, name=None, email=None, cpf=None):
    """Atualiza os dados de um ticket."""
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []

    if name is not None:
        updates.append("name = %s")
        params.append(name)
    if email is not None:
        updates.append("email = %s")
        params.append(email)
    if cpf is not None:
        updates.append("cpf = %s")
        params.append(cpf)

    if updates:
        params.append(code)
        query = f'UPDATE {table} SET {", ".join(updates)} WHERE code = %s'
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        conn.close()
        return cursor.rowcount > 0  # Retorna True se alguma linha foi atualizada

    cursor.close()
    conn.close()
    return False  # Retorna False se não houver atualizações

def delete_ticket(code, table='tickets'):
    """Deleta um ticket pelo código."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'DELETE FROM {table} WHERE code = %s', (code,))
    conn.commit()
    deleted = cursor.rowcount > 0  # Retorna True se uma linha foi deletada
    cursor.close()
    conn.close()
    return deleted

def move_ticket_to_validated(code, table='tickets'):
    """Move um ticket para a tabela de validados."""
    validated_table = 'validated_tickets'
    conn = get_db_connection()
    cursor = conn.cursor()

    # Recupera os dados do ingresso da tabela original
    cursor.execute(f'SELECT * FROM {table} WHERE code = %s', (code,))
    ticket = cursor.fetchone()

    if ticket:
        # Insere os dados do ingresso na tabela 'validated_tickets'
        cursor.execute(f'''
            INSERT INTO {validated_table} (code, name, email, cpf, qr_code_path)
            VALUES (%s, %s, %s, %s, %s)
        ''', (ticket[0], ticket[1], ticket[2], ticket[3], ticket[4]))

        # Deleta o ingresso da tabela original
        cursor.execute(f'DELETE FROM {table} WHERE code = %s', (code,))
        conn.commit()
        cursor.close()
        conn.close()
        return True  # Retorna True se a operação for bem-sucedida

    cursor.close()
    conn.close()
    return False  # Retorna False se o ingresso não for encontrado

def adicionar_lote(nome, descricao, valor, quantidade):
    """Adiciona um novo lote."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO lotes (nome, descricao, valor, quantidade)
        VALUES (%s, %s, %s, %s)
    ''', (nome, descricao, valor, quantidade))
    conn.commit()
    lote_id = cursor.lastrowid  # Retorna o ID do lote adicionado
    cursor.close()
    conn.close()
    return lote_id

def listar_lotes():
    """Lista todos os lotes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM lotes')
    lotes = cursor.fetchall()  # Retorna todos os lotes
    cursor.close()
    conn.close()
    return lotes

def editar_lote(id, nome=None, descricao=None, valor=None, quantidade=None):
    """Edita um lote existente."""
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []

    if nome is not None:
        updates.append("nome = %s")
        params.append(nome)
    if descricao is not None:
        updates.append("descricao = %s")
        params.append(descricao)
    if valor is not None:
        updates.append("valor = %s")
        params.append(valor)
    if quantidade is not None:
        updates.append("quantidade = %s")
        params.append(quantidade)

    if updates:
        params.append(id)
        query = f'UPDATE lotes SET {", ".join(updates)} WHERE id = %s'
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        conn.close()
        return cursor.rowcount > 0  # Retorna True se alguma linha foi atualizada

    cursor.close()
    conn.close()
    return False  # Retorna False se não houver atualizações

def excluir_lote(id):
    """Exclui um lote pelo ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM lotes WHERE id = %s', (id,))
    conn.commit()
    deleted = cursor.rowcount > 0  # Retorna True se uma linha foi deletada
    cursor.close()
    conn.close()
    return deleted

def get_user_tickets(user_id, table='tickets'):
    """Recupera os tickets de um usuário específico na tabela indicada."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f'SELECT * FROM {table} WHERE user_id = %s', (user_id,))
    tickets = cursor.fetchall()  # Retorna todos os tickets encontrados
    cursor.close()
    conn.close()
    return tickets
