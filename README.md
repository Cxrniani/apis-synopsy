# Etternal Nexus Experience — Backend

API do projeto **Etternal Nexus Experience**, desenvolvida com **Python + Flask**, integrada a diversos serviços AWS e Mercado Pago. Responsável por autenticação, gerenciamento de ingressos e integração de pagamentos.


🔗 [Repositório do Frontend](https://github.com/Cxrniani/eternal-nexus-site/tree/master)

---

## 🧰 Tecnologias Utilizadas

- **Flask** (Python 3.11)
- **Amazon Cognito** (autenticação)
- **Amazon DynamoDB** (persistência)
- **Amazon S3** (armazenamento de mídias)
- **Mercado Pago SDK**
- **QRCode** para geração de ingressos
- **Docker** + **EC2**

---

## ⚙️ Funcionalidades

### 👥 Gerenciamento de Usuários

- Cadastro e login via Amazon Cognito
- Sessões seguras e tokens JWT

### 📰 CMS para Notícias e Hero

- Upload de imagens para Amazon S3
- Edição de conteúdo com HTML vindo do Quill.js

### 🎟️ CRUD de Ingressos e Lotes

- Criação e gerenciamento de lotes (admin)
- Consulta pública de lotes disponíveis

### 💳 Integração com Mercado Pago

- Pagamento via PIX ou cartão
- Webhook processa transações aprovadas
- Geração de ingresso com QR Code
- Ingresso é atribuído à conta do usuário

### ✅ Validação de Ingressos

- Leitura de QR Code por administradores
- Ingresso é **marcado como utilizado**
- Ingressos não podem ser reutilizados

---

## 🔐 Segurança

- O backend só aceita requisições da instância do frontend e do Webhook do Mercado Pago
- Verificação de IP e tokens

---

## 🐳 Deploy

- Dockerizado
- Implantado em **instância EC2 privada**
- Comunicação permitida apenas com o frontend e Mercado Pago

---

**Etternal Nexus Experience — Backend** ✨
