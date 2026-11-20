"""Acesso à API, ao Mailpit (códigos OTP) e verificações do estado do reporte."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "http://127.0.0.1:8000"
MAILPIT = "http://127.0.0.1:8025"
CONSENTIMENTO = {"version": "2026-11", "accepted_age": True}


def requisicao(metodo: str, url: str, corpo: dict | None = None, token: str | None = None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resposta:
            texto = resposta.read().decode()
            return resposta.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as erro:
        texto = erro.read().decode()
        try:
            return erro.code, json.loads(texto)
        except json.JSONDecodeError:
            return erro.code, texto


def requisicao_chave(metodo: str, url: str, corpo: dict, chave: str):
    """Chamada da API de órgãos (autenticação por X-API-Key)."""
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method=metodo)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-API-Key", chave)
    try:
        with urllib.request.urlopen(req, timeout=20) as resposta:
            return resposta.status
    except urllib.error.HTTPError as erro:
        return erro.code


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _data_iso(texto: str) -> datetime:
    """ISO 8601 do Mailpit; no Python 3.10 a fração precisa ter 3 ou 6 dígitos."""
    texto = texto.replace("Z", "+00:00")
    texto = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], texto)
    return datetime.fromisoformat(texto)


def codigo_otp(email: str, depois_de: datetime, timeout: float = 30) -> str:
    """Último código enviado a `email` depois do instante informado."""
    consulta = urllib.parse.quote(f'to:"{email}"')
    limite = time.time() + timeout
    while time.time() < limite:
        _, resultado = requisicao("GET", f"{MAILPIT}/api/v1/search?query={consulta}&limit=5")
        for msg in (resultado or {}).get("messages", []):
            criado = _data_iso(msg["Created"])
            m = re.search(r"\b(\d{6})\b", msg.get("Snippet", ""))
            if criado >= depois_de.replace(microsecond=0) and m:
                return m.group(1)
        time.sleep(1)
    raise TimeoutError(f"Nenhum código OTP chegou para {email} no Mailpit.")


def login_api(email: str, cidadao: bool = True) -> str:
    """Login OTP direto pela API (usado só nas verificações e no passo 8)."""
    inicio = agora_utc()
    corpo = {"email": email}
    if cidadao:
        corpo["consent"] = CONSENTIMENTO
    status, _ = requisicao("POST", f"{API}/v1/auth/login", corpo)
    if status not in (200, 202):
        raise RuntimeError(f"Falha ao pedir código para {email}: HTTP {status}")
    codigo = codigo_otp(email, inicio)
    status, sessao = requisicao("POST", f"{API}/v1/auth/login", {"email": email, "code": codigo})
    if status != 200:
        raise RuntimeError(f"Falha no login de {email}: HTTP {status} {sessao}")
    return sessao["access_token"]


def saude() -> bool:
    try:
        status, _ = requisicao("GET", f"{API}/health")
        return status == 200
    except (urllib.error.URLError, OSError):
        return False


def mailpit_ok() -> bool:
    try:
        status, _ = requisicao("GET", f"{MAILPIT}/api/v1/messages?limit=1")
        return status == 200
    except (urllib.error.URLError, OSError):
        return False


def buscar_reporte_staff(token: str, protocolo: str) -> dict | None:
    q = urllib.parse.quote(protocolo)
    status, pagina = requisicao("GET", f"{API}/v1/staff/reports?q={q}&limit=5", token=token)
    if status != 200:
        raise RuntimeError(f"Consulta staff falhou: HTTP {status} {pagina}")
    for item in pagina.get("items", []):
        if item.get("protocol") == protocolo:
            return item
    return None


def detalhe_staff(token: str, report_id: str) -> dict:
    status, corpo = requisicao("GET", f"{API}/v1/staff/reports/{report_id}", token=token)
    if status != 200:
        raise RuntimeError(f"Detalhe staff falhou: HTTP {status} {corpo}")
    return corpo


def esperar(condicao, timeout: float = 60, intervalo: float = 2.0):
    limite = time.time() + timeout
    ultimo = None
    while time.time() < limite:
        ultimo = condicao()
        if ultimo:
            return ultimo
        time.sleep(intervalo)
    return ultimo
