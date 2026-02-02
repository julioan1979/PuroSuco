# Guia de Deploy

## 🚀 Deploy em Produção

### Pré-requisitos

- [ ] Python 3.13+ instalado
- [ ] Servidor com acesso HTTPS
- [ ] Domínio configurado
- [ ] Chaves de produção do Stripe
- [ ] Token do Airtable com permissões corretas
- [ ] BASE_ID validado

## Opções de Deploy

### 1. Deploy com Docker

**Dockerfile**
```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Não copiar .env - usar variáveis de ambiente do host
CMD ["streamlit", "run", "stripe_streamlit_app.py", "--server.port=8501"]
```

**docker-compose.yml**
```yaml
version: '3.8'
services:
  purosuco:
    build: .
    ports:
      - "8501:8501"
    environment:
      - STRIPE_API_KEY=${STRIPE_API_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
      - Airtable_API_Key=${AIRTABLE_API_KEY}
      - Airtable_Base_ID=apppvZnFTV6a33RUf
    restart: unless-stopped
```

**Deploy:**
```bash
# Build
docker-compose build

# Start
docker-compose up -d

# Logs
docker-compose logs -f
```

### 2. Deploy no Streamlit Cloud

1. **Push para GitHub** (sem .env!)
2. **Acesse** https://share.streamlit.io
3. **Conecte** seu repositório
4. **Configure Secrets** em Settings → Secrets:

```toml
# .streamlit/secrets.toml (no Streamlit Cloud)
STRIPE_API_KEY = "sk_live_xxxxx"
STRIPE_WEBHOOK_SECRET = "whsec_xxxxx"
Airtable_API_Key = "patxxxxx"
Airtable_Base_ID = "apppvZnFTV6a33RUf"
```

5. **Deploy** automático!

### 3. Deploy em VPS (Ubuntu)

#### Configuração Inicial

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.13
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.13 python3.13-venv python3.13-dev

# Instalar nginx
sudo apt install nginx

# Instalar supervisor (gerenciador de processos)
sudo apt install supervisor
```

#### Setup da Aplicação

```bash
# Clonar repositório
cd /var/www
git clone https://github.com/seu-usuario/purosuco.git
cd purosuco

# Criar ambiente virtual
python3.13 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
nano .env
# Adicione as variáveis e salve (Ctrl+O, Ctrl+X)
```

#### Configurar Supervisor

```bash
sudo nano /etc/supervisor/conf.d/purosuco.conf
```

```ini
[program:purosuco]
directory=/var/www/purosuco
command=/var/www/purosuco/venv/bin/streamlit run stripe_streamlit_app.py --server.port=8501
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/purosuco/err.log
stdout_logfile=/var/log/purosuco/out.log
environment=PATH="/var/www/purosuco/venv/bin"
```

```bash
# Criar diretório de logs
sudo mkdir /var/log/purosuco

# Recarregar supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start purosuco
```

#### Configurar Nginx

```bash
sudo nano /etc/nginx/sites-available/purosuco
```

```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
# Ativar site
sudo ln -s /etc/nginx/sites-available/purosuco /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### Configurar HTTPS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d seu-dominio.com
```

### 4. Deploy no Heroku

**Procfile**
```
web: streamlit run stripe_streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

**runtime.txt**
```
python-3.13.0
```

**Deploy:**
```bash
# Login
heroku login

# Criar app
heroku create purosuco

# Configurar variáveis
heroku config:set STRIPE_API_KEY=sk_live_xxxxx
heroku config:set STRIPE_WEBHOOK_SECRET=whsec_xxxxx
heroku config:set Airtable_API_Key=patxxxxx
heroku config:set Airtable_Base_ID=apppvZnFTV6a33RUf

# Deploy
git push heroku main

# Ver logs
heroku logs --tail
```

## ⚙️ Configuração de Webhooks

### Stripe Webhooks (Node no Railway)

O webhook em produção roda no serviço Node/Express (arquivo `server.js`) publicado no Railway:

```
https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook
```

1. **Dashboard do Stripe** → Developers → Webhooks
2. **Add endpoint**: `https://stripe-webhook-airtable-production.up.railway.app/stripe/webhook`
3. **Eventos**: Selecione:
   - `charge.succeeded`
   - `charge.failed`
   - `checkout.session.completed`
   - `payout.paid`

4. **Signing secret**: Copie e adicione ao `.env`
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_xxxxx
   ```

5. **Teste**: Envie evento de teste

## 📊 Monitoramento

### Logs

```bash
# Supervisor
sudo tail -f /var/log/purosuco/out.log

# Docker
docker-compose logs -f

# Heroku
heroku logs --tail
```

### Health Check

Adicione endpoint de health:
```python
# stripe_streamlit_app.py
import streamlit as st

# Health check endpoint
if st.query_params.get("health") == "check":
    st.write("OK")
    st.stop()
```

Acesse: `https://seu-dominio.com?health=check`

### Uptime Monitoring

Configure em serviços como:
- UptimeRobot
- Pingdom
- StatusCake

## 🔒 Segurança em Produção

- [ ] HTTPS configurado
- [ ] Firewall ativo (UFW no Ubuntu)
- [ ] Fail2ban instalado
- [ ] Atualizações automáticas de segurança
- [ ] Backups automáticos do .env
- [ ] Rate limiting no nginx
- [ ] Webhooks verificados com assinatura

**Firewall (UFW):**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 🔄 Atualizações

```bash
# Puxar última versão
cd /var/www/purosuco
git pull origin main

# Atualizar dependências
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Reiniciar aplicação
sudo supervisorctl restart purosuco
```

## 📦 Backup

**Script de backup automático:**
```bash
#!/bin/bash
# backup_purosuco.sh

BACKUP_DIR="/backups/purosuco"
DATE=$(date +%Y%m%d_%H%M%S)

# Criar diretório
mkdir -p $BACKUP_DIR

# Backup do .env
cp /var/www/purosuco/.env $BACKUP_DIR/.env_$DATE

# Backup dos logs (últimos 7 dias)
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/purosuco/

# Remover backups antigos (>30 dias)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup concluído: $DATE"
```

**Crontab (diário às 2h):**
```bash
crontab -e
# Adicionar:
0 2 * * * /usr/local/bin/backup_purosuco.sh
```

## 🧪 Testes Pré-Deploy

```bash
# Testes unitários
pytest

# Validação de schema
python apply_airtable_schema.py

# Sincronização de teste (1 registro)
python -c "from sync_data_to_airtable import sync_all_charges; sync_all_charges(limit=1, days_back=1)"
```

## 📞 Suporte

Em caso de problemas, consulte:
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [API.md](API.md)
- Issues no GitHub
