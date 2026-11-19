"""Receptor SMTP de desenvolvimento (substitui o MailHog sem Docker).

Escuta em 127.0.0.1:1025 e imprime no terminal o assunto e o corpo de cada
e-mail recebido, incluindo o código OTP. Uso: python scripts/dev_smtp_sink.py
"""

import socketserver
from email import message_from_string, policy

HOST, PORT = "127.0.0.1", 1025


class SmtpSinkHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        def reply(text: str) -> None:
            self.wfile.write(f"{text}\r\n".encode())

        reply("220 dev-smtp-sink")
        in_data = False
        lines: list[str] = []
        for raw in self.rfile:
            line = raw.decode(errors="ignore").rstrip("\r\n")
            if in_data:
                if line == ".":
                    in_data = False
                    self._print_message("\n".join(lines))
                    lines = []
                    reply("250 ok")
                else:
                    lines.append(line[1:] if line.startswith("..") else line)
                continue
            command = line.upper()
            if command.startswith("DATA"):
                in_data = True
                reply("354 end with <CRLF>.<CRLF>")
            elif command.startswith("QUIT"):
                reply("221 bye")
                return
            else:
                reply("250 ok")

    @staticmethod
    def _print_message(raw: str) -> None:
        message = message_from_string(raw, policy=policy.default)
        body = message.get_body(preferencelist=("plain",))
        print("=" * 60, flush=True)
        print(f"Para:    {message['To']}", flush=True)
        print(f"Assunto: {message['Subject']}", flush=True)
        print(body.get_content().strip() if body else raw, flush=True)
        print("=" * 60, flush=True)


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((HOST, PORT), SmtpSinkHandler) as server:
        print(f"SMTP de desenvolvimento em {HOST}:{PORT}. Aguardando e-mails...", flush=True)
        server.serve_forever()
