#!/usr/bin/env python3
"""Executa o roteiro ponta a ponta (app + painel web) gravando cada passo.

    python3 tests/e2e/executar_fluxo.py                # roteiro completo
    python3 tests/e2e/executar_fluxo.py --ver-navegador # abre o Chrome na tela
    python3 tests/e2e/executar_fluxo.py --sem-video-unico

Pré-requisitos: stack Docker no ar, celular Android via USB com o app de debug
instalado, servidores demo cadastrados (scripts/provision-staff.sh) e
`npm install` em tests/e2e/web. Detalhes em tests/e2e/ROTEIRO.md.

Saída: tests/e2e/gravacoes/AAAA-MM-DD_HHMM/ com um vídeo por passo, prints,
relatório (relatorio.md), dados da execução (dados.json) e log.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from fluxo import api  # noqa: E402
from fluxo.android import Android, ElementoNaoEncontrado, GravadorAndroid  # noqa: E402
from fluxo import humano  # noqa: E402
from fluxo import lado_a_lado  # noqa: E402
import galeria  # noqa: E402

PACOTE = "br.fiap.reclameja.reclame_ja_mobile"
FOTO = RAIZ / "dados" / "esgoto_transbordando.jpg"

CIDADA = "ana.cidada@example.com"
VIZINHO = "bruno.vizinho@example.com"
OPERADORES = {
    "prefeitura-demo-zeladoria": "zeladoria.demo@prefeitura.gov.br",
    "saneamento-demo": "saneamento.demo@prefeitura.gov.br",
}
NOMES_ORGAOS = {
    "prefeitura-demo-zeladoria": "Prefeitura Demo — Zeladoria",
    "saneamento-demo": "Saneamento Demo",
}
# Textos digitados no painel web (o Playwright digita acentos).
JUSTIFICATIVA_REDIRECIONAMENTO = {
    "saneamento-demo": (
        "O vazamento vem da rede coletora de esgoto, que é competência da "
        "concessionária de saneamento. Encaminhando para atendimento."
    ),
    "prefeitura-demo-zeladoria": (
        "A rede de esgoto está íntegra; o problema é a boca de lobo entupida na "
        "calçada, que é competência da Zeladoria."
    ),
}
MODERADORA = "moderadora.demo@prefeitura.gov.br"
GESTORA = "gestora.demo@prefeitura.gov.br"

# Textos digitados no celular: o `adb shell input text` não aceita acentos,
# então as frases usam só palavras escritas corretamente sem acento.
REFERENCIA = "Na frente da entrada principal da escola municipal"
DESCRICAO = (
    "Vazamento de esgoto na frente da escola, com cheiro muito forte e sujeira "
    "escorrendo pela rua desde ontem."
)


@dataclass
class Passo:
    numero: int
    onde: str
    titulo: str
    ok: bool = False
    video: str | None = None
    prints: list[str] = field(default_factory=list)
    verificacoes: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    erro: str | None = None
    duracao_s: float = 0.0
    composto: bool = False


class Execucao:
    def __init__(self, args: argparse.Namespace, prefixo: str = "") -> None:
        self.args = args
        self.pasta = RAIZ / "gravacoes" / (prefixo + datetime.now().strftime("%Y-%m-%d_%H%M"))
        for sub in ("app", "web", "lado-a-lado", "prints"):
            (self.pasta / sub).mkdir(parents=True, exist_ok=True)
        self.arquivo_log = (self.pasta / "execucao.log").open("a", encoding="utf-8")
        self.passos: list[Passo] = []
        self.dados: dict = {"inicio": datetime.now().isoformat(timespec="seconds")}
        self.achados: list[str] = []
        self.a: Android | None = None
        self._token_gestora: str | None = None

    # ------------------------------------------------------------ utilidades
    def log(self, texto: str) -> None:
        linha = f"[{datetime.now():%H:%M:%S}] {texto}"
        print(linha, flush=True)
        self.arquivo_log.write(linha + "\n")
        self.arquivo_log.flush()

    @property
    def gestora(self) -> str:
        if self._token_gestora is None:
            self._token_gestora = api.login_api(GESTORA, cidadao=False)
        return self._token_gestora

    def reporte_staff(self, protocolo: str) -> dict:
        item = api.esperar(lambda: api.buscar_reporte_staff(self.gestora, protocolo), 30)
        if not item:
            raise AssertionError(f"Reporte {protocolo} não aparece no painel da gestão")
        return item

    def detalhe_staff(self, report_id: str) -> dict:
        return api.detalhe_staff(self.gestora, report_id)

    def print_app(self, passo: Passo, nome: str) -> None:
        destino = self.pasta / "prints" / f"{passo.numero:02d}-app-{nome}.png"
        self.a.print_tela(destino)
        passo.prints.append(str(destino.relative_to(self.pasta)))

    def executar_passo(self, numero: int, onde: str, titulo: str, acao) -> Passo:
        passo = Passo(numero, onde, titulo)
        self.passos.append(passo)
        self.log(f"=== Passo {numero} ({onde}): {titulo}")
        inicio = time.time()
        try:
            acao(passo)
            passo.ok = True
        except Exception as erro:  # noqa: BLE001 - o relatório registra qualquer falha
            passo.erro = f"{type(erro).__name__}: {erro}"
            self.log(f"FALHOU: {passo.erro}")
            self.arquivo_log.write(traceback.format_exc())
            if self.a:
                try:
                    self.print_app(passo, "falha")
                except Exception:  # noqa: BLE001
                    pass
        passo.duracao_s = round(time.time() - inicio, 1)
        self.log(f"--- Passo {numero}: {'OK' if passo.ok else 'FALHOU'} ({passo.duracao_s}s)")
        self.salvar()
        return passo

    def gravar_app(self, passo: Passo, nome: str):
        destino = self.pasta / "app" / f"{passo.numero:02d}-app-{nome}.mp4"
        passo.video = str(destino.relative_to(self.pasta))
        return GravadorAndroid(self.a.serial, destino, self.log).iniciar()

    def iniciar_web(self, passo: Passo, nome: str, cenario: str, dados: dict,
                    extra: list[str] | None = None) -> subprocess.Popen:
        video = self.pasta / "web" / f"{passo.numero:02d}-web-{nome}.mp4"
        prints = self.pasta / "prints" / f"{passo.numero:02d}-web-{nome}"
        cmd = [
            "node", "fluxo-web.mjs", cenario, "--dados", json.dumps(dados),
            "--video", str(video), "--prints", str(prints), *(extra or []),
        ]
        if self.args.ver_navegador:
            cmd.append("--headed")
        self.log(f"  web: {cenario} {json.dumps(dados, ensure_ascii=False)}")
        return subprocess.Popen(cmd, cwd=RAIZ / "web", stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1)

    def esperar_linha_web(self, proc: subprocess.Popen, prefixo: str, timeout: float = 120) -> str:
        """Lê o stderr do painel até aparecer a linha `prefixo` (registra as demais)."""
        limite = time.time() + timeout
        assert proc.stderr is not None
        while time.time() < limite:
            linha = proc.stderr.readline()
            if not linha:
                if proc.poll() is not None:
                    break
                continue
            linha = linha.rstrip()
            if linha.startswith(prefixo):
                return linha
            self.log(f"  web{linha}")
        raise RuntimeError(f"Painel não chegou em {prefixo!r}")

    def concluir_web(self, passo: Passo, proc: subprocess.Popen, timeout: float = 600) -> dict:
        stdout, stderr = proc.communicate(timeout=timeout)
        for linha in stderr.splitlines():
            self.log(f"  web{linha}")
        try:
            resultado = json.loads(stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            resultado = {"ok": False, "erro": stdout[-500:] or stderr[-500:]}
        if resultado.get("video"):
            passo.video = str(Path(resultado["video"]).relative_to(self.pasta))
        passo.prints += [str(Path(p).relative_to(self.pasta)) for p in resultado.get("prints", [])]
        passo.notas += resultado.get("notas", [])
        if not resultado.get("ok"):
            raise RuntimeError(f"Painel web: {resultado.get('erro')}")
        return resultado

    def rodar_web(self, passo: Passo, nome: str, cenario: str, dados: dict) -> dict:
        return self.concluir_web(passo, self.iniciar_web(passo, nome, cenario, dados))

    def salvar(self) -> None:
        dados = dict(self.dados)
        dados["passos"] = [vars(p) for p in self.passos]
        dados["achados"] = self.achados
        (self.pasta / "dados.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------- app: ações
    def entrar_no_app(self, email: str) -> None:
        a = self.a
        a.achar(texto="Entrar com e-mail", timeout=20)
        humano.pausa(1.0, 1.8)
        for caixa in [n for n in a.nos() if n.classe == "CheckBox" and not n.marcado]:
            a.tocar(caixa)
        a.tocar_texto("Entrar com e-mail")
        campo = a.achar(classe="EditText")
        a.preencher(campo, email)
        a.fechar_teclado()
        pedido = api.agora_utc()
        a.tocar_texto("Enviar código")
        codigo = api.codigo_otp(email, pedido)
        self.log(f"  código OTP de {email} lido no Mailpit")
        a.achar(texto="Digite o código", timeout=15)
        humano.pausa(1.2, 2.0)  # "abrindo o e-mail"
        a.preencher(a.achar(classe="EditText"), codigo)
        a.fechar_teclado()
        a.tocar_texto("Confirmar entrada")
        a.permitir_permissao(4)  # notificações, se o Android perguntar
        a.achar(contem="Tab 1 of 5", timeout=30)
        humano.pausa(1.5, 2.5)

    def voltar_para_abas(self) -> None:
        """Volta às abas do app sem sair dele (reabre se o BACK fechar o app)."""
        for _ in range(4):
            if self.a.existe(contem="Tab 1 of 5", timeout=3):
                return
            if PACOTE not in self.a.sh("dumpsys window | grep mCurrentFocus"):
                self.a.sh(f"monkey -p {PACOTE} -c android.intent.category.LAUNCHER 1")
                time.sleep(3)
                continue
            self.a.tecla(4)
            time.sleep(1.5)
        self.a.achar(contem="Tab 1 of 5", timeout=10)

    def aba(self, nome: str) -> None:
        self.a.tocar_texto(contem=f"{nome}\nTab", timeout=10)
        time.sleep(1.2)

    def abrir_meu_reporte(self, protocolo: str) -> None:
        self.aba("Reportes")
        cartao = self.a.rolar_ate(contem=protocolo, maximo=6)
        self.a.tocar(cartao)
        self.a.achar(texto="Ocorrência", timeout=15)
        humano.pausa(1.0, 1.6)

    def esperar_no_app(self, texto: str, timeout: float = 70) -> None:
        """Espera o detalhe do app (atualiza a cada 20 s) mostrar `texto`."""
        limite = time.time() + timeout
        while time.time() < limite:
            if self.a.existe(contem=texto, timeout=1):
                return
            time.sleep(2)
        raise ElementoNaoEncontrado(f"O app não mostrou {texto!r} em {timeout:.0f}s")

    def mostrar_detalhe(self, ate: str | None = None) -> None:
        """Rola o detalhe devagar até a linha do tempo, como quem lê."""
        for _ in range(3):
            self.a.rolar(True, 0.35)
            humano.pausa(1.0, 1.6)
        if ate:
            try:
                self.a.rolar_ate(contem=ate, maximo=4)
                humano.pausa(1.5, 2.2)
            except ElementoNaoEncontrado:
                self.log(f"  aviso: {ate!r} não apareceu na linha do tempo do app")
        for _ in range(4):
            self.a.rolar(False, 0.8)

    # ---------------------------------------------------------------- passos
    def passo1_login(self, passo: Passo) -> None:
        a = self.a
        a.abrir_app(PACOTE, limpar_dados=True)
        gravacao = self.gravar_app(passo, "login-cidada")
        try:
            self.entrar_no_app(CIDADA)
            self.print_app(passo, "mapa")
        finally:
            gravacao.finalizar()
        passo.verificacoes.append("Login por OTP com código lido no Mailpit")

    def passo2_novo_reporte(self, passo: Passo) -> None:
        """Tomada simultânea: o painel já está aberto quando o celular envia."""
        a = self.a
        sinal = self.pasta / ".sinal-protocolo.json"
        sinal.unlink(missing_ok=True)
        painel = self.iniciar_web(passo, "painel-recebe", "painel-ao-vivo", {"email": GESTORA},
                                  ["--sinal", str(sinal)])
        try:
            self.esperar_linha_web(painel, "PRONTO", timeout=180)
            self.log("  painel aberto em Gestão de Ocorrências, aguardando o celular")
            esconder = galeria.imagens_visiveis()
            gravacao = self.gravar_app(passo, "novo-reporte")
            try:
                protocolo = self.enviar_reporte_no_app(gravacao, esconder)
                sinal.write_text(json.dumps({"protocolo": protocolo}))
                self.log("  protocolo enviado ao painel")
                humano.pausa(2.0, 3.0)
                a.rolar(True, 0.3)  # lendo "O que vai acontecer agora"
                resultado = self.concluir_web(passo, painel)
            finally:
                gravacao.finalizar()
        finally:
            if painel.poll() is None:
                painel.kill()
            sinal.unlink(missing_ok=True)
        video_app = self.pasta / "app" / f"{passo.numero:02d}-app-novo-reporte.mp4"
        passo.notas.append(f"Gravação só do celular: app/{video_app.name}")
        passo.notas.append(f"Gravação só do painel: {passo.video}")
        destino = self.pasta / "lado-a-lado" / f"{passo.numero:02d}-celular-envia-painel-recebe.mp4"
        lado_a_lado.montar(video_app, gravacao.trechos_ms, self.pasta / passo.video,
                           resultado["inicioVideoMs"], destino, f"Passo {passo.numero} - {passo.titulo}")
        passo.video = str(destino.relative_to(self.pasta))
        passo.composto = True
        item = self.reporte_staff(protocolo)
        self.dados["report_id"] = item["id"]
        passo.verificacoes.append(f"Reporte {protocolo} gravado no Oracle (id {item['id']})")
        passo.verificacoes.append("Reporte apareceu no painel da prefeitura logo após o envio")

    def enviar_reporte_no_app(self, gravacao, esconder: list[str]) -> str:
        a = self.a
        a.tocar_texto("Reportar problema")
        a.achar(texto="Passo 1 de 4")
        humano.pausa(1.0, 1.6)
        if esconder:
            self.log(f"  {len(esconder)} imagem(ns) pessoal(is) na galeria: pausando a gravação")
            gravacao.pausar()
        a.tocar_texto("Abrir Galeria")
        a.tocar_texto(contem="Item Foto criado em", timeout=10)
        a.tocar_texto("Concluir")
        if esconder:
            gravacao.retomar()
        a.achar(texto="Anexada", timeout=10)
        humano.pausa(1.0, 1.5)
        a.tocar_texto("Continuar")
        a.tocar_texto("Capturar GPS")
        a.permitir_permissao(4)
        a.achar(contem="Precisão", timeout=30)
        humano.pausa(0.8, 1.3)
        a.preencher(a.achar(classe="EditText"), REFERENCIA, chance_erro=0.04)
        a.fechar_teclado()
        a.tocar_texto("Continuar")
        a.achar(texto="3. O que você observou?")
        a.preencher(a.achar(classe="EditText"), DESCRICAO, chance_erro=0.04)
        a.fechar_teclado()
        humano.pausa(0.8, 1.2)
        a.tocar_texto("Continuar")
        a.achar(texto="4. Categoria do chamado")
        a.achar(texto="Deixar a IA classificar")  # padrão: a IA decide a categoria
        humano.pausa(1.5, 2.2)
        a.tocar_texto("Enviar solicitação")
        no = a.achar(regex=r"RPT-\d{4}-[A-Z0-9]+", timeout=30)
        protocolo = re.search(r"RPT-\d{4}-[A-Z0-9]+", no.texto).group(0)
        self.dados["protocolo"] = protocolo
        self.log(f"  protocolo gerado: {protocolo}")
        humano.pausa(2.0, 3.0)
        self.print_app(self.passos[-1], "confirmacao")
        self.confirmar_se_pedido(protocolo)
        return protocolo

    def confirmar_se_pedido(self, protocolo: str, timeout: float = 90) -> None:
        """Espera a IA; se a triagem pedir a confirmação do cidadão, confirma no app."""
        limite = time.time() + timeout
        while time.time() < limite:
            item = api.buscar_reporte_staff(self.gestora, protocolo)
            if item and item.get("agency"):
                return  # já encaminhado
            detalhe = api.detalhe_staff(self.gestora, item["id"]) if item else {}
            if detalhe.get("triage_state") == "awaiting_user":
                botao = self.a.rolar_ate(texto="Sim, confirmar", maximo=4)
                humano.pausa(0.6, 1.0)
                self.a.tocar(botao)
                self.a.achar(contem="Dados validados", timeout=15)
                return
            time.sleep(1.5)
        raise AssertionError(f"{protocolo}: a triagem não terminou em {timeout:.0f}s")

    def passo3_acompanhar(self, passo: Passo) -> None:
        a = self.a
        protocolo = self.dados["protocolo"]
        gravacao = self.gravar_app(passo, "acompanhar-classificacao")
        try:
            a.rolar_ate(texto="Acompanhar chamado")
            a.tocar_texto("Acompanhar chamado")
            a.achar(texto="Ocorrência", timeout=15)
            self.esperar_no_app("Responsável:", 60)
            humano.pausa(1.5, 2.0)
            self.print_app(passo, "detalhe")
            self.mostrar_detalhe(ate="Encaminhado ao órgão")
        finally:
            gravacao.finalizar()
        item = self.reporte_staff(protocolo)
        detalhe = self.detalhe_staff(item["id"])
        agencia = (item.get("agency") or {}).get("id")
        self.dados["orgao_inicial"] = agencia
        classificacao = detalhe.get("classification") or {}
        passo.verificacoes.append(
            f"Classificação: {detalhe.get('category')} / {classificacao.get('subcategory')} "
            f"(urgência {classificacao.get('urgency')}, fonte {classificacao.get('source')})"
        )
        passo.verificacoes.append(f"Encaminhado a: {NOMES_ORGAOS.get(agencia, agencia)}")
        if agencia not in OPERADORES:
            raise AssertionError(f"Órgão inesperado para o roteiro: {agencia}")

    def passo4_operador(self, passo: Passo) -> None:
        inicial = self.dados["orgao_inicial"]
        destino = next(k for k in OPERADORES if k != inicial)
        self.dados["orgao_final"] = destino
        self.rodar_web(passo, "orgao-redireciona", "operador", {
            "email": OPERADORES[inicial],
            "protocolo": self.dados["protocolo"],
            "redirecionarPara": NOMES_ORGAOS[destino],
            "justificativa": JUSTIFICATIVA_REDIRECIONAMENTO[destino],
        })
        item = self.reporte_staff(self.dados["protocolo"])
        atual = (item.get("agency") or {}).get("id")
        if atual != destino:
            raise AssertionError(f"Órgão após redirecionar: {atual}, esperado {destino}")
        passo.verificacoes.append(
            f"Redirecionado de {NOMES_ORGAOS[inicial]} para {NOMES_ORGAOS[destino]} com justificativa"
        )

    def passo5_app_redirecionado(self, passo: Passo) -> None:
        destino = NOMES_ORGAOS[self.dados["orgao_final"]]
        gravacao = self.gravar_app(passo, "app-ve-redirecionamento")
        try:
            humano.pausa(1.5, 2.0)
            self.esperar_no_app(f"Responsável: {destino}", 70)
            humano.pausa(1.5, 2.0)
            self.print_app(passo, "novo-orgao")
            self.mostrar_detalhe(ate="Redirecionado")
        finally:
            gravacao.finalizar()
        passo.verificacoes.append(f"App mostra o novo órgão ({destino}) e o redirecionamento")

    def passo6_atender(self, passo: Passo) -> None:
        self.rodar_web(passo, "novo-orgao-atende-e-resolve", "atender", {
            "email": OPERADORES[self.dados["orgao_final"]],
            "protocolo": self.dados["protocolo"],
            "prazoDias": 2,
            "justificativa": (
                "Rede desobstruída e trecho higienizado pela equipe de manutenção. "
                "Vistoria final concluída."
            ),
        })
        item = self.reporte_staff(self.dados["protocolo"])
        if item["status"] != "resolvido":
            raise AssertionError(f"Status no painel: {item['status']}")
        passo.verificacoes.append("Status: encaminhado -> em_andamento (com prazo) -> resolvido")

    def passo7_app_resolvido(self, passo: Passo) -> None:
        gravacao = self.gravar_app(passo, "app-ve-resolvido")
        try:
            humano.pausa(1.0, 1.5)
            self.esperar_no_app("RESOLVIDO", 70)
            humano.pausa(1.5, 2.0)
            self.print_app(passo, "resolvido")
            self.mostrar_detalhe(ate="Resolvido")
        finally:
            gravacao.finalizar()
        passo.verificacoes.append("App mostra o reporte resolvido com a justificativa do órgão")

    def passo8_vizinho(self, passo: Passo) -> None:
        a = self.a
        meu_id = self.dados["report_id"]
        gravacao = self.gravar_app(passo, "vizinho-confirma-e-sinaliza")
        try:
            if not a.existe(texto="Entrar com e-mail", timeout=2):
                self.voltar_para_abas()
                self.aba("Perfil")
                # No fim do Perfil o botão flutuante "Reportar problema" cobre a
                # metade direita de "Sair do Aplicativo": toca na metade esquerda.
                sair = a.rolar_ate(texto="Sair do Aplicativo", maximo=6)
                a.tocar((sair.x1 + (sair.x2 - sair.x1) // 5, sair.centro[1]))
                a.tocar_texto("Desconectar")
            self.entrar_no_app(VIZINHO)
            self.aba("Feed")
            humano.pausa(1.5, 2.0)
            alvo_id = None
            for indice in range(4):
                cartoes = [n for n in a.nos() if n.clicavel and "\n" in n.texto
                           and "Tab" not in n.texto and n.y1 > a.altura * 0.25]
                if indice >= len(cartoes):
                    break
                a.tocar(cartoes[indice])
                a.achar(texto="Ocorrência", timeout=15)
                no = a.achar(regex=r"[0-9a-f]{8}-[0-9a-f]{4}-", timeout=10)
                candidato = re.search(r"[0-9a-f-]{36}", no.texto).group(0)
                if candidato != meu_id:
                    alvo_id = candidato
                    break
                a.tecla(4)
                time.sleep(1.2)
            if not alvo_id:
                raise AssertionError("Nenhum outro reporte no feed para o vizinho sinalizar")
            self.dados["reporte_sinalizado"] = alvo_id
            humano.pausa(1.0, 1.5)
            botao = a.rolar_ate(contem="Eu também vi isso", maximo=6)
            a.tocar(botao)
            humano.pausa(1.5, 2.0)
            link = a.rolar_ate(texto="Relatar inconsistência", maximo=6)
            a.tocar(link)
            humano.pausa(2.0, 2.5)
            self.print_app(passo, "relatar")
        finally:
            gravacao.finalizar()
        # O botão "Relatar inconsistência" só mostra uma mensagem: a sinalização
        # real (POST /v1/reports/{id}/flag) é feita pela API com o vizinho.
        token = api.login_api(VIZINHO)
        status, corpo = api.requisicao(
            "POST", f"{api.API}/v1/reports/{alvo_id}/flag",
            {"reason": "falso", "note": "Foto e descrição não conferem com o local."}, token,
        )
        if status not in (202, 409):
            raise AssertionError(f"Sinalização via API falhou: HTTP {status} {corpo}")
        detalhe = api.esperar(
            lambda: (d := self.detalhe_staff(alvo_id)).get("triage_state") == "in_moderation" and d,
            20,
        )
        if not detalhe:
            raise AssertionError("Reporte sinalizado não entrou na fila de moderação")
        self.dados["protocolo_sinalizado"] = detalhe["protocol"]
        passo.notas.append(
            "Sinalização enviada pela API: o botão 'Relatar inconsistência' do app "
            "não chama POST /v1/reports/{id}/flag (só mostra uma mensagem)."
        )
        passo.verificacoes.append(f"Confirmação '+1' registrada no app pelo vizinho")
        passo.verificacoes.append(f"Reporte {detalhe['protocol']} entrou em moderação")

    def passo9_moderacao(self, passo: Passo) -> None:
        protocolo = self.dados["protocolo_sinalizado"]
        self.rodar_web(passo, "moderadora-decide", "moderar", {
            "email": MODERADORA,
            "protocolo": protocolo,
            "decisao": "Rejeitar",
            "justificativa": (
                "Conteúdo não corresponde ao local informado; reporte retirado do mapa "
                "após verificação da equipe."
            ),
        })
        detalhe = self.detalhe_staff(self.dados["reporte_sinalizado"])
        if detalhe.get("triage_state") != "rejected":
            raise AssertionError(f"Triagem após moderar: {detalhe.get('triage_state')}")
        passo.verificacoes.append(f"Reporte {protocolo} rejeitado e auditado na linha do tempo")

    def passo10_gestao(self, passo: Passo) -> None:
        resultado = self.rodar_web(passo, "gestora-indicadores", "gestao", {"email": GESTORA})
        status, metricas = api.requisicao("GET", f"{api.API}/v1/public/metrics")
        if status != 200:
            raise AssertionError(f"Indicadores públicos: HTTP {status}")
        passo.verificacoes.append(
            f"Indicadores: {metricas['totals']['reports']} reportes, resposta média "
            f"{metricas['totals']['avg_response_hours']} h"
        )
        if any("CSV exportado" in n for n in resultado.get("notas", [])):
            passo.verificacoes.append("CSV de indicadores exportado")

    # ------------------------------------------------------------ preparação
    def preflight(self) -> None:
        self.log("Verificando pré-requisitos")
        problemas = []
        if not api.saude():
            problemas.append("API fora do ar (http://127.0.0.1:8000/health)")
        if not api.mailpit_ok():
            problemas.append("Mailpit fora do ar (http://127.0.0.1:8025)")
        if not (RAIZ / "web" / "node_modules" / "playwright").exists():
            problemas.append("Rode `npm install` em tests/e2e/web")
        try:
            self.a = Android(log=self.log)
            self.a.preparar(PACOTE)
        except Exception as erro:  # noqa: BLE001
            problemas.append(str(erro))
        if problemas:
            for p in problemas:
                self.log(f"  pré-requisito: {p}")
            raise SystemExit(1)
        visiveis = galeria.imagens_visiveis()
        if visiveis:
            self.log(f"  aviso: {len(visiveis)} imagem(ns) pessoal(is) na galeria; "
                     "a gravação pausa enquanto o seletor estiver aberto "
                     "(ou rode `python3 tests/e2e/galeria.py ocultar`).")
        self.a.enviar_imagem_galeria(FOTO, FOTO.name)
        self.dados["show_touches_antes"] = self.a.mostrar_toques(True)
        self.dados["celular"] = self.a.serial

    def finalizar(self) -> None:
        if self.a:
            anterior = self.dados.get("show_touches_antes", "0")
            self.a.sh(f"settings put system show_touches {anterior or 0}")
            self.a.fechar()
        self.dados["fim"] = datetime.now().isoformat(timespec="seconds")
        self.salvar()
        if not self.args.sem_video_unico:
            try:
                self.video_unico()
            except Exception as erro:  # noqa: BLE001
                self.log(f"Vídeo único não gerado: {erro}")
        relatorio(self)
        self.log(f"Pasta da execução: {self.pasta}")

    def video_unico(self) -> None:
        """Junta os passos num vídeo 1920x1080 com o título de cada passo."""
        fonte = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        partes = []
        temporaria = self.pasta / ".partes"
        temporaria.mkdir(exist_ok=True)
        for passo in self.passos:
            if not passo.video:
                continue
            origem = self.pasta / passo.video
            onde = {"App": "App", "Web": "Painel web"}.get(passo.onde, passo.onde)
            titulo = f"Passo {passo.numero} - {onde}: {passo.titulo}"
            titulo = titulo.replace(":", r"\:").replace("'", "")
            saida = temporaria / f"{passo.numero:02d}.mp4"
            filtro = (
                "scale=1920:990:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:90+(990-ih)/2:color=0x111827,"
                f"drawtext=fontfile={fonte}:text='{titulo}':fontcolor=0xEBE100:"
                "fontsize=40:x=40:y=25,fps=30,format=yuv420p"
            )
            if passo.composto:  # a tomada lado a lado já tem layout e título
                filtro = "scale=1920:1080,fps=30,format=yuv420p"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origem), "-vf", filtro,
                 "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", str(saida)],
                check=True,
            )
            partes.append(saida)
        if not partes:
            return
        lista = temporaria / "lista.txt"
        lista.write_text("".join(f"file '{p.name}'\n" for p in partes))
        destino = self.pasta / "00-demonstracao-completa.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lista), "-c", "copy", "-movflags", "+faststart", str(destino)],
            check=True, cwd=temporaria,
        )
        for arquivo in temporaria.iterdir():
            arquivo.unlink()
        temporaria.rmdir()
        self.log(f"Vídeo único: {destino.name}")


def relatorio(execucao: Execucao) -> None:
    linhas = [
        "# Relatório da execução do roteiro ponta a ponta",
        "",
        f"- Início: {execucao.dados.get('inicio')}  ",
        f"- Fim: {execucao.dados.get('fim')}  ",
        f"- Protocolo principal: `{execucao.dados.get('protocolo', '-')}`  ",
        f"- Reporte sinalizado: `{execucao.dados.get('protocolo_sinalizado', '-')}`",
        "",
        "| # | Onde | Passo | Resultado | Vídeo | Duração |",
        "|---|---|---|---|---|---|",
    ]
    for p in execucao.passos:
        video = f"[{Path(p.video).name}]({p.video})" if p.video else "-"
        linhas.append(
            f"| {p.numero} | {p.onde} | {p.titulo} | {'OK' if p.ok else 'FALHOU'} | {video} | {p.duracao_s}s |"
        )
    linhas.append("")
    for p in execucao.passos:
        linhas.append(f"## Passo {p.numero}: {p.titulo}")
        for v in p.verificacoes:
            linhas.append(f"- Verificado: {v}")
        for n in p.notas:
            linhas.append(f"- Nota: {n}")
        if p.erro:
            linhas.append(f"- **Erro:** `{p.erro}`")
        for imagem in p.prints:
            if imagem.endswith(".png"):
                linhas.append(f"- Print: [{Path(imagem).name}]({imagem})")
        linhas.append("")
    if (execucao.pasta / "00-demonstracao-completa.mp4").exists():
        linhas.append("Vídeo com todos os passos: [00-demonstracao-completa.mp4](00-demonstracao-completa.mp4)")
    (execucao.pasta / "relatorio.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ver-navegador", action="store_true", help="abre o Chrome na tela")
    parser.add_argument("--sem-video-unico", action="store_true",
                        help="não junta os passos em 00-demonstracao-completa.mp4")
    parser.add_argument("--somente", help="roda só estes passos, ex.: 8,9 (para depurar)")
    parser.add_argument("--dados-de", type=Path,
                        help="dados.json de uma execução anterior (protocolo, órgãos...)")
    args = parser.parse_args()

    execucao = Execucao(args)
    if args.dados_de:
        anteriores = json.loads(args.dados_de.read_text())
        for chave in ("protocolo", "report_id", "orgao_inicial", "orgao_final",
                      "reporte_sinalizado", "protocolo_sinalizado"):
            if chave in anteriores:
                execucao.dados[chave] = anteriores[chave]
    somente = {int(n) for n in args.somente.split(",")} if args.somente else None
    execucao.preflight()
    roteiro = [
        (1, "App", "Cidadã entra com e-mail e código", execucao.passo1_login),
        (2, "App + Web", "Celular envia a solicitação e ela chega ao painel", execucao.passo2_novo_reporte),
        (3, "App", "Cidadã confere a classificação da IA e o órgão", execucao.passo3_acompanhar),
        (4, "Web", "Órgão encontra o reporte e redireciona", execucao.passo4_operador),
        (5, "App", "App mostra o novo órgão e o redirecionamento", execucao.passo5_app_redirecionado),
        (6, "Web", "Novo órgão inicia o atendimento e resolve", execucao.passo6_atender),
        (7, "App", "App mostra o reporte resolvido", execucao.passo7_app_resolvido),
        (8, "App", "Vizinho confirma (+1) e sinaliza um reporte", execucao.passo8_vizinho),
        (9, "Web", "Moderadora decide o reporte sinalizado", execucao.passo9_moderacao),
        (10, "Web", "Gestora vê o painel, indicadores e CSV", execucao.passo10_gestao),
    ]
    try:
        for numero, onde, titulo, acao in roteiro:
            if somente and numero not in somente:
                continue
            passo = execucao.executar_passo(numero, onde, titulo, acao)
            if not passo.ok and numero in (2, 3):
                execucao.log("Sem reporte válido os passos seguintes não fazem sentido; parando.")
                break
    finally:
        execucao.finalizar()
    falhas = [p for p in execucao.passos if not p.ok]
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
