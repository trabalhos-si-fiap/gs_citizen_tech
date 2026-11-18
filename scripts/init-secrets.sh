#!/usr/bin/env sh
# Gera os arquivos de segredo usados pelo docker compose (Docker secrets).
# Não sobrescreve arquivos existentes. A pasta secrets/ é ignorada pelo git.
set -eu
cd "$(dirname "$0")/.."
mkdir -p secrets
chmod 700 secrets

random() {
    # Alfanumérico: aceito como senha Oracle sem aspas.
    LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"
}

create() {
    file="secrets/$1.txt"
    if [ -f "$file" ]; then
        echo "mantido: $file"
        return
    fi
    printf '%s' "$2" >"$file"
    # 644: o compose (sem Swarm) monta o arquivo com as permissões do host e
    # os processos rodam com UID sem privilégio. A pasta (700) protege no host.
    chmod 644 "$file"
    echo "criado:  $file"
}

create oracle_password "O$(random 23)"
create db_password "A$(random 23)"
create jwt_secret "$(random 48)"
create photo_upload_secret "$(random 48)"
create agency_api_keys "$(random 32)"
