#!/usr/bin/env python3
"""Grava a demo curta (até 2 min 30 s) com celular e painel lado a lado.

    python3 tests/e2e/gravar_demo.py
    python3 tests/e2e/gravar_demo.py --ver-navegador

Roteiro (tempo-alvo de cada cena entre parênteses):
  abertura (5 s) -> cidadã registra e o painel recebe (60 s) ->
  órgão atende e resolve enquanto o app atualiza (40 s) ->
  gestão e indicadores públicos (37 s) -> encerramento (8 s).

Logins, código OTP e preparação ficam fora da gravação. Mesmos pré-requisitos
de `executar_fluxo.py` (ROTEIRO.md). Saída em tests/e2e/gravacoes/demo_<data>/,
com o vídeo final `00-demo-2min30-sem-narracao.mp4` (e, com `narrar.py`, `00-demo-2min30-com-narracao.mp4`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import executar_fluxo as base  # noqa: E402
from fluxo import api, humano, lado_a_lado, montagem  # noqa: E402

LIMITE_S = 150.0
ALVOS = {"abertura": 5.0, "cena1": 60.0, "cena2": 40.0, "cena3": 35.0, "encerramento": 8.0}
RITMO_WEB = "1.4"
RITMO_CELULAR = 1.5

TITULOS = {
    "cena1": "1. O cidadão registra o problema; a IA classifica e encaminha ao órgão",
    "cena2": "2. O órgão atende e resolve; o cidadão acompanha no app",
    "cena3": "3. Gestão pública com dados: órgãos, prazos e indicadores abertos",
}
DESCRICAO_DEMO = "Vazamento de esgoto na frente da escola, com cheiro muito forte."
JUSTIFICATIVA_DEMO = "Rede desobstruída e calçada higienizada. Serviço concluído."


class Demo(base.Execucao):
    """Reaproveita o orquestrador completo, mas grava só as cenas da demo."""

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(args, prefixo="demo_")
        (self.pasta / "cenas").mkdir(exist_ok=True)

    # ------------------------------------------------------- preparo (sem câmera)
    def preparar(self) -> None:
        self.preflight()
        self.encerrar_ensaios_anteriores()
        self.a.velocidade = RITMO_CELULAR
        self.log("Preparo fora da gravação: login da cidadã no app")
        self.a.abrir_app(base.PACOTE, limpar_dados=True)
        self.entrar_no_app(base.CIDADA)
        self.aba("Mapa")

    def encerrar_ensaios_anteriores(self) -> None:
        """Resolve os reportes abertos da cidadã de demonstração.

        Sem isso, o reporte novo (mesmo lugar, mesmo texto) é agrupado como
        duplicata de um ensaio anterior e não aparece sozinho no painel.
        Só mexe nos reportes da conta de demonstração.
        """
        token = api.login_api(base.CIDADA)
        _, pagina = api.requisicao("GET", f"{api.API}/v1/me/reports?limit=100", token=token)
        abertos = [i for i in pagina.get("items", []) if i["status"] != "resolvido"]
        chave = (RAIZ.parents[1] / "secrets" / "agency_api_keys.txt").read_text().split(",")[0].strip()
        for item in abertos:
            rid = item["id"]
            _, detalhe = api.requisicao("GET", f"{api.API}/v1/reports/{rid}", token=token)
            if detalhe.get("triage_state") == "awaiting_user":
                api.requisicao("POST", f"{api.API}/v1/reports/{rid}/triage", {"action": "confirm"}, token)
            encaminhado = api.esperar(
                lambda: (api.requisicao("GET", f"{api.API}/v1/reports/{rid}", token=token)[1]
                         .get("agency")), 30, 1.5)
            if not encaminhado:
                self.log(f"  ensaio {item['protocol']}: sem órgão (membro de grupo?), mantido")
                continue
            prazo = (base.datetime.now(base.timezone.utc) + base.timedelta(days=1)).isoformat()
            for corpo in ({"action": "in_progress", "deadline": prazo},
                          {"action": "resolved", "justification": "Reporte de ensaio da demonstração."}):
                api.requisicao_chave("POST", f"{api.API}/v1/agency/reports/{rid}/status", corpo, chave)
            self.log(f"  ensaio anterior encerrado: {item['protocol']}")

    def sinal(self, arquivo: Path, **dados) -> None:
        arquivo.write_text(json.dumps(dados))

    # ------------------------------------------------------------------ cenas
    def cena1(self, passo: base.Passo) -> None:
        """Lado a lado: o celular envia e o painel (gestora) recebe."""
        sinal = self.pasta / ".sinal.json"
        sinal.unlink(missing_ok=True)
        painel = self.iniciar_web(passo, "cena1-painel", "demo-chegada", {"email": base.GESTORA},
                                  ["--sinal", str(sinal), "--ritmo", RITMO_WEB])
        try:
            self.esperar_linha_web(painel, "PRONTO", timeout=180)
            gravacao = self.gravar_app(passo, "cena1-celular")
            try:
                protocolo = self.registrar_no_app()
                item = api.esperar(lambda: self._visivel_no_painel(protocolo), 90, 1)
                if not item:
                    raise AssertionError(f"{protocolo} não chegou ao painel")
                self.sinal(sinal, protocolo=protocolo)
                resultado = self.concluir_web(passo, painel)
            finally:
                gravacao.finalizar()
        finally:
            if painel.poll() is None:
                painel.kill()
            sinal.unlink(missing_ok=True)
        self.dados["orgao"] = (item.get("agency") or {}).get("id")
        destino = self.pasta / "cenas" / "cena1.mp4"
        lado_a_lado.montar(self.pasta / "app" / f"{passo.numero:02d}-app-cena1-celular.mp4",
                           gravacao.trechos_ms, self.pasta / passo.video, resultado["inicioVideoMs"],
                           destino, TITULOS["cena1"])
        passo.video = str(destino.relative_to(self.pasta))
        passo.verificacoes.append(f"{protocolo} classificado e encaminhado a {self.dados['orgao']}")

    def _visivel_no_painel(self, protocolo: str) -> dict | None:
        item = api.buscar_reporte_staff(self.gestora, protocolo)
        return item if item and item.get("agency") else None

    def registrar_no_app(self) -> str:
        """Fluxo do assistente no celular, com textos curtos para caber na demo."""
        a = self.a
        a.tocar_texto("Reportar problema")
        a.achar(texto="Passo 1 de 4")
        a.tocar_texto("Abrir Galeria")
        a.tocar_texto(contem="Item Foto criado em", timeout=10)
        a.tocar_texto("Concluir")
        a.achar(texto="Anexada", timeout=10)
        a.tocar_texto("Continuar")
        a.tocar_texto("Capturar GPS")
        a.permitir_permissao(4)
        a.achar(contem="Precisão", timeout=30)
        humano.pausa(0.6, 0.9)
        a.tocar_texto("Continuar")
        a.achar(texto="3. O que você observou?")
        campo = a.achar(classe="EditText")
        a.preencher(campo, DESCRICAO_DEMO)
        a.fechar_teclado()
        a.tocar_texto("Continuar")
        a.achar(texto="4. Categoria do chamado")
        humano.pausa(0.8, 1.2)
        a.tocar_texto("Enviar solicitação")
        no = a.achar(regex=r"RPT-\d{4}-[A-Z0-9]+", timeout=30)
        protocolo = re.search(r"RPT-\d{4}-[A-Z0-9]+", no.texto).group(0)
        self.dados["protocolo"] = protocolo
        self.log(f"  protocolo: {protocolo}")
        self.confirmar_se_pedido(protocolo)
        humano.pausa(1.5, 2.0)
        return protocolo

    def cena2(self, passo: base.Passo) -> None:
        """Lado a lado: o órgão atende e resolve; o app reabre o reporte a cada mudança."""
        protocolo = self.dados["protocolo"]
        orgao = self.dados.get("orgao")
        if orgao not in base.OPERADORES:
            raise AssertionError(f"Sem operador demo para o órgão {orgao!r}")
        self.voltar_para_abas()
        self.aba("Reportes")
        cartao = self.a.rolar_ate(contem=protocolo, maximo=4)
        sinal = self.pasta / ".sinal.json"
        sinal.unlink(missing_ok=True)
        painel = self.iniciar_web(passo, "cena2-orgao", "demo-atender",
                                  {"email": base.OPERADORES[orgao], "protocolo": protocolo,
                                   "justificativa": JUSTIFICATIVA_DEMO},
                                  ["--sinal", str(sinal), "--ritmo", RITMO_WEB])
        try:
            self.esperar_linha_web(painel, "PRONTO", timeout=180)
            gravacao = self.gravar_app(passo, "cena2-celular")
            try:
                self.a.tocar(cartao)
                self.a.achar(texto="Ocorrência", timeout=15)
                for etapa, texto in (("em_andamento", "EM ANDAMENTO"), ("resolvido", "RESOLVIDO")):
                    self.esperar_linha_web(painel, f"STATUS {etapa}", timeout=180)
                    self.reabrir_detalhe(protocolo, texto)
                    self.sinal(sinal, protocolo=protocolo, etapa=etapa)
                resultado = self.concluir_web(passo, painel)
            finally:
                gravacao.finalizar()
        finally:
            if painel.poll() is None:
                painel.kill()
            sinal.unlink(missing_ok=True)
        destino = self.pasta / "cenas" / "cena2.mp4"
        lado_a_lado.montar(self.pasta / "app" / f"{passo.numero:02d}-app-cena2-celular.mp4",
                           gravacao.trechos_ms, self.pasta / passo.video, resultado["inicioVideoMs"],
                           destino, TITULOS["cena2"])
        passo.video = str(destino.relative_to(self.pasta))
        passo.verificacoes.append("Status no app: em andamento -> resolvido")

    def reabrir_detalhe(self, protocolo: str, status: str) -> None:
        """Volta à lista (que já mostra o status novo) e reabre o detalhe."""
        self.a.tecla(4)
        limite = time.time() + 30
        while time.time() < limite:
            cartao = self.a.rolar_ate(contem=protocolo, maximo=2)
            if status.casefold() in cartao.texto.casefold() or time.time() > limite - 20:
                break
            time.sleep(2)  # a lista atualiza sozinha
        humano.pausa(0.8, 1.2)
        self.a.tocar(self.a.rolar_ate(contem=protocolo, maximo=2))
        self.esperar_no_app(status, 30)
        humano.pausa(1.2, 1.6)

    def cena3(self, passo: base.Passo) -> None:
        self.rodar_web(passo, "cena3-gestao", "demo-gestao", {"email": base.GESTORA})
        destino = self.pasta / "cenas" / "cena3.mp4"
        montagem.com_faixa(self.pasta / passo.video, destino, TITULOS["cena3"])
        passo.video = str(destino.relative_to(self.pasta))

    # ---------------------------------------------------------------- montagem
    def montar_demo(self) -> Path:
        cenas = self.pasta / "cenas"
        partes = [montagem.cartao(cenas / "abertura.mp4", "Reclame Já",
                                  ["Do celular do cidadão ao órgão responsável,",
                                   "com IA e transparência."], ALVOS["abertura"])]
        for chave in ("cena1", "cena2", "cena3"):
            ajustada, fator = montagem.no_tempo(cenas / f"{chave}.mp4", cenas / f"{chave}-final.mp4",
                                                ALVOS[chave])
            self.log(f"  {chave}: {montagem.duracao(cenas / f'{chave}.mp4'):.1f}s gravados, "
                     f"acelerada {fator:.2f}x -> {montagem.duracao(ajustada):.1f}s")
            partes.append(ajustada)
        partes.append(montagem.cartao(
            cenas / "encerramento.mp4", "Reclame Já",
            ["IA classifica o relato  •  encaminha ao órgão certo",
             "cidadão acompanha  •  gestão com indicadores públicos",
             "FIAP Global Solution 2026  •  Citizen Tech"], ALVOS["encerramento"]))
        destino = self.pasta / "00-demo-2min30-sem-narracao.mp4"
        montagem.emendar(partes, destino)
        total = montagem.duracao(destino)
        self.dados["duracao_demo_s"] = round(total, 1)
        self.log(f"Demo: {destino.name} com {total:.1f}s (limite {LIMITE_S:.0f}s)")
        if total > LIMITE_S + 0.5:
            self.log("ATENÇÃO: passou do limite; aumente RITMO_* ou a aceleração máxima.")
        return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ver-navegador", action="store_true")
    args = parser.parse_args()
    args.sem_video_unico = True
    demo = Demo(args)
    demo.preparar()
    cenas = [(1, "App + Web", "Cidadão registra; painel recebe", demo.cena1),
             (2, "App + Web", "Órgão resolve; app acompanha", demo.cena2),
             (3, "Web", "Gestão e indicadores", demo.cena3)]
    try:
        for numero, onde, titulo, acao in cenas:
            passo = demo.executar_passo(numero, onde, titulo, acao)
            if not passo.ok:
                break
        if all(p.ok for p in demo.passos) and len(demo.passos) == len(cenas):
            demo.montar_demo()
    finally:
        demo.finalizar()
    sys.exit(0 if all(p.ok for p in demo.passos) else 1)


if __name__ == "__main__":
    main()
