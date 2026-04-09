#!/bin/bash
set -e

TOKEN_FILE="/data/admin_token.txt"
HOMESERVER_URL="http://synapse:3000"

DB_HOST="postgres"
DB_USER="userDoDB"
DB_NAME="synapse"
DB_PASSWORD="senhaDoDB"

EMAIL="emailDoAdmin@email.com"
PASSWORD='senhaDoAdmin'

echo "Removendo token antigo (se existir)..."
rm -f "$TOKEN_FILE"

echo "Esperando Synapse subir..."
until curl -s "$HOMESERVER_URL/_matrix/client/versions" > /dev/null; do
  sleep 2
done

echo "Fazendo login via RestAuthProvider..."

RESPONSE=$(curl -s -X POST "$HOMESERVER_URL/_matrix/client/v3/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"m.login.password\",
    \"identifier\": {
      \"type\": \"m.id.user\",
      \"user\": \"$EMAIL\"
    },
    \"password\": \"$PASSWORD\"
  }")

echo "Resposta: $RESPONSE"

ACCESS_TOKEN=$(echo "$RESPONSE" | jq -r '.access_token')
USER_ID=$(echo "$RESPONSE" | jq -r '.user_id')

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
  echo "Erro ao logar via paywall"
  exit 1
fi

echo "Login OK: $USER_ID"

echo "Tornando usuário admin global..."

PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c \
"UPDATE users SET admin = 1 WHERE name = '$USER_ID';"

echo "Salvando token..."

echo "$ACCESS_TOKEN" > "$TOKEN_FILE"
chmod 644 "$TOKEN_FILE"

echo "Setup completo: usuário é admin + token salvo"
echo "Setup completo — mantendo container vivo..."

tail -f /dev/null
