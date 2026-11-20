# Fontes dos testes de layout

Cópias exatas dos arquivos que o pacote `google_fonts` baixa e guarda no
aparelho (nome `<família>_<variante>_<sha256>.ttf`, o mesmo do cache do app).
Os testes em `test/support/phone.dart` apontam a pasta de suporte do app para
cá, então o texto é medido com as métricas reais, sem acesso à rede.

Origem: Google Fonts (`https://fonts.gstatic.com/s/a/<sha256>.ttf`).
Licenças: Hanken Grotesk, Space Grotesk e JetBrains Mono são distribuídas sob a
SIL Open Font License 1.1.

Se um teste falhar com "google_fonts was unable to load font X", a tela usa uma
variante que ainda não está aqui: baixe-a pela URL do erro e salve com o nome
`<Família>_<variante>_<hash>.ttf` (o hash é o próprio nome do arquivo na URL).
