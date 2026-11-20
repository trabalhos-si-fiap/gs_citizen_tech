"""Controle do celular Android via ADB, com toques e digitação "humanos".

- Elementos são localizados pela árvore de acessibilidade (`uiautomator dump`),
  que no Flutter expõe textos e rótulos dos widgets.
- A digitação usa um `adb shell` persistente, uma tecla por vez, com o ritmo
  de `humano.py`.
- A gravação usa o scrcpy sem janela (sem limite de 3 min do screenrecord) e
  pode ser pausada (por exemplo, enquanto a galeria de fotos pessoais está
  aberta); os trechos são unidos com ffmpeg no final.
"""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import humano

KEY_SPACE = 62
KEY_DEL = 67
KEY_FORWARD_DEL = 112
KEY_BACK = 4
KEY_ENTER = 66

_PERMISSAO_IDS = (
    "com.android.permissioncontroller:id/permission_allow_foreground_only_button",
    "com.android.permissioncontroller:id/permission_allow_button",
    "com.android.permissioncontroller:id/permission_allow_one_time_button",
)


class ElementoNaoEncontrado(RuntimeError):
    pass


@dataclass
class No:
    texto: str
    classe: str
    rid: str
    clicavel: bool
    focado: bool
    marcado: bool
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def centro(self) -> tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    @property
    def visivel(self) -> bool:
        return self.x2 > self.x1 and self.y2 > self.y1

    @property
    def linhas(self) -> list[str]:
        return [linha.strip() for linha in self.texto.splitlines() if linha.strip()]

    def __str__(self) -> str:
        return f"{self.classe}({self.texto[:50]!r} @ {self.centro})"


class Android:
    def __init__(
        self,
        serial: str | None = None,
        log: Callable[[str], None] = print,
        velocidade_digitacao: float = 1.0,
    ) -> None:
        self.serial = serial or self._primeiro_dispositivo()
        self.log = log
        self.velocidade = velocidade_digitacao
        self._shell: subprocess.Popen | None = None
        self.largura, self.altura = self._tamanho_tela()

    # ------------------------------------------------------------------ adb
    def _adb(self) -> list[str]:
        return ["adb", "-s", self.serial]

    @staticmethod
    def _primeiro_dispositivo() -> str:
        saida = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, check=True
        ).stdout
        seriais = [
            linha.split()[0]
            for linha in saida.splitlines()[1:]
            if linha.strip().endswith("device")
        ]
        if not seriais:
            raise RuntimeError("Nenhum celular conectado via ADB (adb devices).")
        return seriais[0]

    def sh(self, comando: str, timeout: float = 30) -> str:
        return subprocess.run(
            [*self._adb(), "shell", comando],
            capture_output=True,
            text=True,
            timeout=timeout,
        ).stdout

    def _tamanho_tela(self) -> tuple[int, int]:
        m = re.search(r"(\d+)x(\d+)", self.sh("wm size"))
        return (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)

    def _shell_persistente(self) -> subprocess.Popen:
        if self._shell is None or self._shell.poll() is not None:
            self._shell = subprocess.Popen(
                [*self._adb(), "shell"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        return self._shell

    def _enviar(self, comando: str) -> None:
        shell = self._shell_persistente()
        assert shell.stdin is not None
        shell.stdin.write(comando + "\n")
        shell.stdin.flush()

    def _sincronizar(self) -> None:
        """Espera o shell persistente terminar os comandos enfileirados."""
        shell = self._shell_persistente()
        assert shell.stdin is not None and shell.stdout is not None
        shell.stdin.write("echo __FIM__\n")
        shell.stdin.flush()
        while "__FIM__" not in (shell.stdout.readline() or "__FIM__"):
            pass

    def fechar(self) -> None:
        if self._shell and self._shell.poll() is None:
            self._shell.terminate()

    # ------------------------------------------------------------ preparo
    def preparar(self, pacote: str, porta_api: int = 8000) -> None:
        subprocess.run([*self._adb(), "reverse", f"tcp:{porta_api}", f"tcp:{porta_api}"],
                       check=True, capture_output=True)
        self.sh("input keyevent KEYCODE_WAKEUP")
        self.sh("wm dismiss-keyguard")
        if pacote not in self.sh(f"pm list packages {pacote}"):
            raise RuntimeError(f"App {pacote} não está instalado no celular.")

    def mostrar_toques(self, ligado: bool) -> str:
        anterior = self.sh("settings get system show_touches").strip()
        self.sh(f"settings put system show_touches {1 if ligado else 0}")
        return anterior

    def abrir_app(self, pacote: str, limpar_dados: bool = False) -> None:
        self.sh(f"am force-stop {pacote}")
        if limpar_dados:
            self.sh(f"pm clear {pacote}")
        self.sh(f"monkey -p {pacote} -c android.intent.category.LAUNCHER 1")
        time.sleep(2.5)

    def enviar_imagem_galeria(self, origem: Path, nome: str) -> str:
        destino = f"/sdcard/Pictures/ReclameJaTeste/{nome}"
        self.sh("mkdir -p /sdcard/Pictures/ReclameJaTeste")
        subprocess.run([*self._adb(), "push", str(origem), destino], check=True,
                       capture_output=True)
        self.sh(f"touch {destino}")
        self.sh(
            "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE "
            f"-d file://{destino}"
        )
        time.sleep(1.5)
        return destino

    # --------------------------------------------------------- leitura de tela
    def nos(self, tentativas: int = 4) -> list[No]:
        for _ in range(tentativas):
            saida = subprocess.run(
                [*self._adb(), "exec-out", "uiautomator", "dump", "/dev/tty"],
                capture_output=True, text=True, timeout=30,
            ).stdout
            inicio = saida.find("<?xml")
            fim = saida.rfind("</hierarchy>")
            if inicio >= 0 and fim > inicio:
                raiz = ET.fromstring(saida[inicio:fim + len("</hierarchy>")])
                resultado = []
                for n in raiz.iter("node"):
                    m = re.findall(r"\d+", n.get("bounds", ""))
                    if len(m) != 4:
                        continue
                    resultado.append(No(
                        texto=n.get("content-desc") or n.get("text") or "",
                        classe=(n.get("class") or "").split(".")[-1],
                        rid=n.get("resource-id") or "",
                        clicavel=n.get("clickable") == "true",
                        focado=n.get("focused") == "true",
                        marcado=n.get("checked") == "true",
                        x1=int(m[0]), y1=int(m[1]), x2=int(m[2]), y2=int(m[3]),
                    ))
                return resultado
            time.sleep(0.8)  # tela animando; tenta de novo
        return []

    def texto_tela(self) -> str:
        return "\n".join(n.texto for n in self.nos() if n.texto)

    def achar(
        self,
        texto: str | None = None,
        *,
        contem: str | None = None,
        regex: str | None = None,
        classe: str | None = None,
        rid: str | None = None,
        indice: int = 0,
        timeout: float = 15,
    ) -> No:
        alvo = texto or contem or regex or classe or rid
        limite = time.time() + timeout
        while True:
            candidatos = [n for n in self.nos() if n.visivel]
            if classe:
                candidatos = [n for n in candidatos if n.classe == classe]
            if rid:
                candidatos = [n for n in candidatos if n.rid == rid]
            if texto is not None:
                candidatos = [
                    n for n in candidatos
                    if n.texto.strip() == texto or texto in n.linhas
                ]
            if contem is not None:
                c = contem.casefold()
                candidatos = [n for n in candidatos if c in n.texto.casefold()]
            if regex is not None:
                candidatos = [n for n in candidatos if re.search(regex, n.texto)]
            if len(candidatos) > indice:
                return candidatos[indice]
            if time.time() > limite:
                raise ElementoNaoEncontrado(f"Elemento não encontrado: {alvo!r}")
            time.sleep(0.5)

    def existe(self, **kwargs) -> bool:
        try:
            self.achar(timeout=kwargs.pop("timeout", 2), **kwargs)
            return True
        except ElementoNaoEncontrado:
            return False

    def esperar_sumir(self, timeout: float = 20, **kwargs) -> None:
        limite = time.time() + timeout
        while self.existe(timeout=0.5, **kwargs):
            if time.time() > limite:
                raise TimeoutError(f"Elemento não sumiu: {kwargs}")
            time.sleep(0.5)

    # --------------------------------------------------------------- ações
    def tocar(self, alvo: No | tuple[int, int], pausa_antes: bool = True) -> None:
        x, y = alvo.centro if isinstance(alvo, No) else alvo
        if pausa_antes:
            humano.pausa(0.35, 0.9)
        self.sh(f"input tap {x} {y}")
        time.sleep(0.35)

    def tocar_texto(self, texto: str | None = None, **kwargs) -> No:
        no = self.achar(texto, **kwargs)
        self.log(f"  toque: {no}")
        self.tocar(no)
        return no

    def segurar(self, alvo: No, ms: int = 900) -> None:
        x, y = alvo.centro
        self.sh(f"input swipe {x} {y} {x} {y} {ms}")

    def rolar(self, para_baixo: bool = True, fracao: float = 0.45) -> None:
        x = self.largura // 2
        meio = int(self.altura * 0.55)
        delta = int(self.altura * fracao / 2)
        y1, y2 = (meio + delta, meio - delta) if para_baixo else (meio - delta, meio + delta)
        self.sh(f"input swipe {x} {y1} {x} {y2} 450")
        time.sleep(0.7)

    def rolar_ate(
        self, maximo: int = 8, para_baixo: bool = True, ate_y: float = 0.88, **kwargs
    ) -> No:
        """Rola até o elemento ficar visível acima de `ate_y` (fração da altura);
        use um valor menor quando há botão flutuante cobrindo a parte de baixo."""
        for _ in range(maximo):
            try:
                no = self.achar(timeout=1, **kwargs)
                if no.y2 < self.altura * ate_y and no.y1 > self.altura * 0.08:
                    return no
            except ElementoNaoEncontrado:
                pass
            self.rolar(para_baixo)
        return self.achar(timeout=2, **kwargs)

    def tecla(self, codigo: int | str) -> None:
        self.sh(f"input keyevent {codigo}")

    def teclado_aberto(self) -> bool:
        return "mInputShown=true" in self.sh("dumpsys input_method | grep mInputShown")

    def fechar_teclado(self) -> None:
        if self.teclado_aberto():
            humano.pausa(0.3, 0.6)
            self.tecla(KEY_BACK)
            time.sleep(0.5)

    def digitar(self, texto: str, chance_erro: float = 0.0) -> None:
        """Digita no campo focado, tecla a tecla, em ritmo humano."""
        texto_ascii = humano.sem_acentos(texto)
        if texto_ascii != texto:
            self.log(f"  aviso: acentos removidos para o ADB: {texto_ascii!r}")
        anterior = ""
        for acao, c in humano.plano_digitacao(texto_ascii, chance_erro):
            if acao == "hesita":
                time.sleep(humano.random.uniform(0.25, 0.6))
                continue
            if acao == "apaga":
                self._enviar(f"input keyevent {KEY_DEL}")
            elif c == " ":
                self._enviar(f"input keyevent {KEY_SPACE}")
            elif c == "'":
                self._enviar("input keyevent 75")
            else:
                self._enviar(f"input text '{c}'")
            time.sleep(humano.intervalo_tecla(anterior, self.velocidade))
            anterior = c
        self._sincronizar()

    def limpar_focado(self, maximo: int = 400) -> None:
        """Apaga o conteúdo do campo focado, onde quer que esteja o cursor.

        Ctrl+A não é confiável no Flutter e MOVE_END só vai até o fim da linha
        em campos multilinha; então apaga para trás (DEL) e para a frente
        (FORWARD_DEL) numa rajada, como quem segura o backspace.
        """
        time.sleep(humano.random.uniform(0.3, 0.6))
        self.sh("input keyevent " + " ".join([str(KEY_DEL)] * maximo))
        self.sh("input keyevent " + " ".join([str(KEY_FORWARD_DEL)] * maximo))
        time.sleep(0.3)

    def preencher(
        self, campo: No, texto: str, chance_erro: float = 0.0, limpar: bool = True
    ) -> None:
        self.log(f"  digitando em {campo}: {texto!r}")
        self.tocar(campo)
        time.sleep(0.4)
        if limpar and campo.texto:
            self.limpar_focado(len(campo.texto) + 5)
        self.digitar(texto, chance_erro)

    def permitir_permissao(self, timeout: float = 4) -> bool:
        limite = time.time() + timeout
        while time.time() < limite:
            for no in self.nos():
                if no.rid in _PERMISSAO_IDS:
                    self.log("  permissão do Android concedida")
                    self.tocar(no)
                    return True
            time.sleep(0.5)
        return False

    def print_tela(self, destino: Path) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("wb") as arquivo:
            subprocess.run([*self._adb(), "exec-out", "screencap", "-p"],
                           stdout=arquivo, check=True)
        return destino


def duracao_video(arquivo: Path) -> float:
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(arquivo)],
        capture_output=True, text=True,
    ).stdout.strip()
    return float(saida or 0)


class GravadorAndroid:
    """Grava a tela via scrcpy (sem janela). Suporta pausar/retomar."""

    def __init__(self, serial: str, destino: Path, log: Callable[[str], None] = print):
        self.serial = serial
        self.destino = destino
        self.log = log
        self._trechos: list[Path] = []
        self._processo: subprocess.Popen | None = None
        # Horário (epoch, ms) e duração (s) de cada trecho gravado, para
        # sincronizar com a gravação do painel web.
        self.trechos_ms: list[tuple[float, float]] = []
        self._inicio_trecho_ms = 0.0

    def _iniciar_trecho(self) -> None:
        trecho = self.destino.with_name(
            f"{self.destino.stem}.parte{len(self._trechos) + 1}.mp4"
        )
        self._trechos.append(trecho)
        self._processo = subprocess.Popen(
            [
                "scrcpy", "-s", self.serial, "--no-window", "--no-audio",
                "--no-control", "--max-fps=30", "--video-bit-rate=8M",
                f"--record={trecho}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        limite = time.time() + 10
        while time.time() < limite:
            if trecho.exists() and trecho.stat().st_size > 0:
                break
            time.sleep(0.1)
        self._inicio_trecho_ms = time.time() * 1000
        time.sleep(0.8)

    def _parar_trecho(self) -> None:
        if self._processo and self._processo.poll() is None:
            time.sleep(0.6)
            self._processo.send_signal(signal.SIGINT)
            try:
                self._processo.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._processo.kill()
            trecho = self._trechos[-1]
            if trecho.exists() and trecho.stat().st_size > 0:
                self.trechos_ms.append((self._inicio_trecho_ms, duracao_video(trecho)))
        self._processo = None

    def iniciar(self) -> "GravadorAndroid":
        self.destino.parent.mkdir(parents=True, exist_ok=True)
        self._iniciar_trecho()
        return self

    def pausar(self) -> None:
        self._parar_trecho()

    def retomar(self) -> None:
        self._iniciar_trecho()

    def finalizar(self) -> Path:
        self._parar_trecho()
        trechos = [t for t in self._trechos if t.exists() and t.stat().st_size > 0]
        if not trechos:
            raise RuntimeError("Gravação vazia.")
        if len(trechos) == 1:
            shutil.move(trechos[0], self.destino)
        else:
            lista = self.destino.with_suffix(".txt")
            lista.write_text("".join(f"file '{t.name}'\n" for t in trechos))
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lista), "-c", "copy", str(self.destino)],
                check=True, cwd=lista.parent,
            )
            lista.unlink()
            for t in trechos:
                t.unlink()
        self.log(f"  gravação salva: {self.destino}")
        return self.destino
