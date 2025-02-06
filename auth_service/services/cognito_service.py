import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError
import jwt  # Importe a biblioteca jwt
import re

load_dotenv()

class CognitoService:
    def __init__(self):
        self.client = boto3.client(
            "cognito-idp",
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        self.user_pool_id = os.getenv("AWS_COGNITO_USER_POOL_ID")
        self.client_id = os.getenv("AWS_COGNITO_CLIENT_ID")
    
    def check_email_exists(self, email):
        try:
            response = self.client.list_users(
                UserPoolId=self.user_pool_id,
                Filter=f'email = "{email}"'
            )
            exists = len(response["Users"]) > 0
            return {"exists": exists}
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])
    
    def sign_up(self, email, password, name):
            # Validação de senha
        if not re.match(r"^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?\":{}|<>])[A-Za-z\d!@#$%^&*(),.?\":{}|<>]{8,}$", password):
            raise Exception("A senha não atende aos requisitos mínimos")
        try:
            response = self.client.sign_up(
                ClientId=self.client_id,
                Username=email,
                Password=password,
                UserAttributes=[{"Name": "name", "Value": name}, {"Name": "email", "Value": email}],
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])

    def confirm_sign_up(self, email, code):
        try:
            response = self.client.confirm_sign_up(
                ClientId=self.client_id,
                Username=email,
                ConfirmationCode=code,
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])

    def login(self, email, password):
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                },
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])

    def logout(self, access_token):
        try:
            response = self.client.global_sign_out(
                AccessToken=access_token,
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])

    def get_user(self, access_token):
        try:
            response = self.client.get_user(
                AccessToken=access_token,
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])
    def forgot_password(self, email):
        try:
            response = self.client.forgot_password(
                ClientId=self.client_id,
                Username=email
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])
    def confirm_forgot_password(self, email, code, new_password):
        try:
            response = self.client.confirm_forgot_password(
                ClientId=self.client_id,
                Username=email,
                ConfirmationCode=code,
                Password=new_password
            )
            return response
        except ClientError as e:
            raise Exception(e.response["Error"]["Message"])
        
    def get_user_by_email(self, email):
        """
        Busca um usuário no Amazon Cognito pelo email e retorna seus detalhes.
        
        :param email: Email do usuário a ser buscado.
        :return: Dicionário com os detalhes do usuário ou uma mensagem de erro.
        """
        try:
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=email
            )
            
            # Extrai os atributos do usuário
            user_attributes = response.get("UserAttributes", [])
            user_details = {attr["Name"]: attr["Value"] for attr in user_attributes}
            
            return {
                "status": "success",
                "user": {
                    "username": response.get("Username"),
                    "enabled": response.get("Enabled"),
                    "user_status": response.get("UserStatus"),
                    "created_at": response.get("UserCreateDate"),
                    "modified_at": response.get("UserLastModifiedDate"),
                    **user_details
                }
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "UserNotFoundException":
                return {"status": "error", "message": "Usuário não encontrado"}
            raise Exception(e.response["Error"]["Message"])
    