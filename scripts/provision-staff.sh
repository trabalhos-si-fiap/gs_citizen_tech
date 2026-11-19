#!/bin/sh
# Cadastra um servidor no Oracle do docker compose (login depois por OTP).
#
#   ./scripts/provision-staff.sh servidor@prefeitura.gov.br agency prefeitura-demo-zeladoria
#   ./scripts/provision-staff.sh moderadora@prefeitura.gov.br moderator
#
# Papéis: agency (exige órgão), manager, moderator, admin.
set -eu

if [ "$#" -lt 2 ]; then
    echo "uso: $0 EMAIL PAPEL [ORGAO]" >&2
    exit 64
fi

email=$1
role=$2
agency=${3:--}
case "$role" in
    agency) [ "$agency" != "-" ] || { echo "papel agency exige o órgão" >&2; exit 64; } ;;
    manager | moderator | admin) ;;
    *) echo "papel inválido: $role" >&2; exit 64 ;;
esac
case "$email" in
    *[!A-Za-z0-9@._+-]*) echo "e-mail com caracteres não permitidos" >&2; exit 64 ;;
esac

cd "$(dirname "$0")/.."
app_user=$(grep -E '^ORACLE_APP_USER=' .env 2>/dev/null | cut -d= -f2)
app_user=${app_user:-reclameja}

docker compose cp back-end/db/provision_staff.sql oracle:/tmp/provision_staff.sql >/dev/null
# A senha é lida do Docker secret dentro do container, fora da linha de comando.
docker compose exec -T oracle bash -c \
    "sqlplus -s \"$app_user/\$(cat /run/secrets/db_password)@localhost/FREEPDB1\" @/tmp/provision_staff.sql '$email' '$role' '$agency' </dev/null"
