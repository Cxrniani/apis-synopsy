import os
import boto3
from botocore.exceptions import ClientError, WaiterError
from dotenv import load_dotenv
from decimal import Decimal
import uuid

load_dotenv()

# Configurações do DynamoDB
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
AWS_REGION = os.environ['AWS_REGION']

# Inicializa o cliente do DynamoDB
dynamodb = boto3.resource(
    'dynamodb',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Nomes das tabelas
TICKETS_TABLE = 'tickets'
LOTES_TABLE = 'lotes'
VALIDATED_TICKETS_TABLE = 'validated_tickets'

def ensure_table_exists():
    """Cria as tabelas se não existirem."""
    try:
        # Tabela de tickets
        dynamodb.create_table(
            TableName=TICKETS_TABLE,
            KeySchema=[
                {'AttributeName': 'event_id', 'KeyType': 'HASH'},  # Partition key
                {'AttributeName': 'code', 'KeyType': 'RANGE'}      # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'event_id', 'AttributeType': 'S'},
                {'AttributeName': 'code', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        waiter = dynamodb.meta.client.get_waiter('table_exists')
        waiter.wait(TableName=TICKETS_TABLE, WaiterConfig={'Delay': 2, 'MaxAttempts': 10})
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceInUseException':
            raise

    try:
        # Tabela de lotes
        dynamodb.create_table(
            TableName=LOTES_TABLE,
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'N'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        waiter = dynamodb.meta.client.get_waiter('table_exists')
        waiter.wait(TableName=LOTES_TABLE, WaiterConfig={'Delay': 2, 'MaxAttempts': 10})
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceInUseException':
            raise
    try:
        # Tabela de saldo e saques
        dynamodb.create_table(
            TableName='admin_balance',
            KeySchema=[
                {'AttributeName': 'admin_id', 'KeyType': 'HASH'}  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'admin_id', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        waiter = dynamodb.meta.client.get_waiter('table_exists')
        waiter.wait(TableName='admin_balance', WaiterConfig={'Delay': 2, 'MaxAttempts': 10})
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceInUseException':
            raise

    try:
        # Tabela de tickets validados
        dynamodb.create_table(
            TableName=VALIDATED_TICKETS_TABLE,
            KeySchema=[
                {'AttributeName': 'event_id', 'KeyType': 'HASH'},  # Partition key
                {'AttributeName': 'code', 'KeyType': 'RANGE'}      # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'event_id', 'AttributeType': 'S'},
                {'AttributeName': 'code', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        waiter = dynamodb.meta.client.get_waiter('table_exists')
        waiter.wait(TableName=VALIDATED_TICKETS_TABLE, WaiterConfig={'Delay': 2, 'MaxAttempts': 10})
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceInUseException':
            raise

def store_ticket(event_id, code, name, email, cpf, user_id, price, lot):
    """Armazena um ticket no DynamoDB."""
    table = dynamodb.Table(TICKETS_TABLE)
    try:
        table.put_item(
            Item={
                'event_id': event_id,
                'code': code,
                'name': name,
                'email': email,
                'cpf': cpf,
                'user_id': user_id,
                'price': price,
                'lot': lot
            },
            ConditionExpression='attribute_not_exists(code)'  # Evita duplicação de tickets
        )
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return False  # Código já existe
        raise

def get_ticket(event_id, code):
    """Recupera um ticket pelo event_id e código."""
    table = dynamodb.Table(TICKETS_TABLE)
    response = table.get_item(Key={'event_id': event_id, 'code': code})
    return response.get('Item')

def get_all_tickets(event_id):
    """Recupera todos os tickets de um evento."""
    table = dynamodb.Table(TICKETS_TABLE)
    response = table.query(
        KeyConditionExpression='event_id = :event_id',
        ExpressionAttributeValues={':event_id': event_id}
    )
    return response.get('Items', [])

def update_ticket(event_id, code, name=None, email=None, cpf=None):
    """Atualiza os dados de um ticket."""
    table = dynamodb.Table(TICKETS_TABLE)
    update_expression = []
    expression_attribute_values = {}

    if name is not None:
        update_expression.append('SET #name = :name')
        expression_attribute_values[':name'] = name
    if email is not None:
        update_expression.append('SET #email = :email')
        expression_attribute_values[':email'] = email
    if cpf is not None:
        update_expression.append('SET #cpf = :cpf')
        expression_attribute_values[':cpf'] = cpf

    if update_expression:
        response = table.update_item(
            Key={'event_id': event_id, 'code': code},
            UpdateExpression=', '.join(update_expression),
            ExpressionAttributeNames={
                '#name': 'name',
                '#email': 'email',
                '#cpf': 'cpf'
            },
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='UPDATED_NEW'
        )
        return response.get('Attributes') is not None
    return False

def delete_ticket(event_id, code):
    """Deleta um ticket pelo event_id e código."""
    table = dynamodb.Table(TICKETS_TABLE)
    response = table.delete_item(Key={'event_id': event_id, 'code': code})
    return response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200

def move_ticket_to_validated(event_id, code):
    """Move um ticket para a tabela de validados."""
    tickets_table = dynamodb.Table(TICKETS_TABLE)
    validated_table = dynamodb.Table(VALIDATED_TICKETS_TABLE)

    # Recupera o ticket da tabela original
    ticket = tickets_table.get_item(Key={'event_id': event_id, 'code': code}).get('Item')
    if ticket:
        # Insere o ticket na tabela de validados
        validated_table.put_item(Item=ticket)
        # Remove o ticket da tabela original
        tickets_table.delete_item(Key={'event_id': event_id, 'code': code})
        return True
    return False

def adicionar_lote(nome, descricao, valor, quantidade):
    """Adiciona um novo lote."""
    table = dynamodb.Table(LOTES_TABLE)
    try:
        # Gera um ID incremental
        last_id = max([item['id'] for item in table.scan()['Items']]) if table.scan()['Count'] > 0 else 0
        new_id = last_id + 1
    except KeyError:
        new_id = 1

    table.put_item(
        Item={
            'id': new_id,
            'nome': nome,
            'descricao': descricao,
            'valor': valor,
            'quantidade': quantidade
        }
    )
    return new_id

def listar_lotes():
    """Lista todos os lotes."""
    table = dynamodb.Table(LOTES_TABLE)
    response = table.scan()
    return response.get('Items', [])

def editar_lote(id, nome=None, descricao=None, valor=None, quantidade=None):
    """Edita um lote existente."""
    table = dynamodb.Table(LOTES_TABLE)
    update_expression = []
    expression_attribute_values = {}

    if nome is not None:
        update_expression.append('SET #nome = :nome')
        expression_attribute_values[':nome'] = nome
    if descricao is not None:
        update_expression.append('SET #descricao = :descricao')
        expression_attribute_values[':descricao'] = descricao
    if valor is not None:
        update_expression.append('SET #valor = :valor')
        expression_attribute_values[':valor'] = valor
    if quantidade is not None:
        update_expression.append('SET #quantidade = :quantidade')
        expression_attribute_values[':quantidade'] = quantidade

    if update_expression:
        response = table.update_item(
            Key={'id': id},
            UpdateExpression=', '.join(update_expression),
            ExpressionAttributeNames={
                '#nome': 'nome',
                '#descricao': 'descricao',
                '#valor': 'valor',
                '#quantidade': 'quantidade'
            },
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='UPDATED_NEW'
        )
        return response.get('Attributes') is not None
    return False

def excluir_lote(id):
    """Exclui um lote pelo ID."""
    table = dynamodb.Table(LOTES_TABLE)
    response = table.delete_item(Key={'id': id})
    return response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200

def get_user_tickets(user_id, event_id=None):
    """Recupera os tickets de um usuário."""
    table = dynamodb.Table(TICKETS_TABLE)
    if event_id:
        response = table.scan(
            FilterExpression='user_id = :user_id AND event_id = :event_id',
            ExpressionAttributeValues={':user_id': user_id, ':event_id': event_id}
        )
    else:
        response = table.scan(
            FilterExpression='user_id = :user_id',
            ExpressionAttributeValues={':user_id': user_id}
        )
    return response.get('Items', [])

def get_admin_balance(admin_id):
    """Recupera o saldo do administrador."""
    table = dynamodb.Table('admin_balance')
    response = table.get_item(Key={'admin_id': admin_id})
    if 'Item' in response:
        return response['Item'].get('balance', Decimal('0'))
    return Decimal('0')

def update_admin_balance(admin_id, amount):
    """Atualiza o saldo do administrador."""
    table = dynamodb.Table('admin_balance')
    try:
        table.update_item(
            Key={'admin_id': admin_id},
            UpdateExpression='SET balance = if_not_exists(balance, :zero) + :amount',
            ExpressionAttributeValues={':amount': Decimal(str(amount)), ':zero': Decimal('0')},
            ReturnValues='UPDATED_NEW'
        )
        return True
    except ClientError as e:
        print(f"Erro ao atualizar saldo: {e}")
        return False

def add_withdrawal_request(admin_id, amount):
    """Adiciona uma solicitação de saque."""
    table = dynamodb.Table('admin_balance')
    try:
        table.update_item(
            Key={'admin_id': admin_id},
            UpdateExpression='SET withdrawal_requests = list_append(if_not_exists(withdrawal_requests, :empty_list), :request)',
            ExpressionAttributeValues={
                ':request': [{'amount': Decimal(str(amount)), 'status': 'pending'}],
                ':empty_list': []
            },
            ReturnValues='UPDATED_NEW'
        )
        return True
    except ClientError as e:
        print(f"Erro ao adicionar solicitação de saque: {e}")
        return False

def mark_withdrawal_as_done(admin_id, index):
    """Marca um saque como realizado."""
    table = dynamodb.Table('admin_balance')
    try:
        table.update_item(
            Key={'admin_id': admin_id},
            UpdateExpression=f'SET withdrawal_requests[{index}].#status = :done',
            ExpressionAttributeNames={
                '#status': 'status'  # Mapeia a palavra reservada "status" para um alias
            },
            ExpressionAttributeValues={':done': 'done'},
            ReturnValues='UPDATED_NEW'
        )
        return True
    except ClientError as e:
        print(f"Erro ao marcar saque como realizado: {e}")
        return False
