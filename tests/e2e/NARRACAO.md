# Narração da demo (2 min 28 s)

A montagem deixa cada bloco com duração fixa, então a narração pode ser gravada
por bloco e encaixada nos tempos abaixo. Os tempos internos de cada bloco são
aproximados (± 3 s), porque a IA e a rede variam a cada gravação.

Ritmo de referência: cerca de 140 palavras por minuto, com respiro entre frases.

| Bloco | Tempo | Duração |
|---|---|---|
| Abertura | 0:00 – 0:05 | 5 s |
| Cena 1: cidadão registra | 0:05 – 1:05 | 60 s |
| Cena 2: órgão resolve | 1:05 – 1:45 | 40 s |
| Cena 3: gestão e indicadores | 1:45 – 2:20 | 35 s |
| Encerramento | 2:20 – 2:28 | 8 s |

## Abertura (0:00 – 0:05)

> Reclame Já: do celular do cidadão ao órgão responsável, com IA e transparência.

## Cena 1: o cidadão registra o problema (0:05 – 1:05)

- **0:05 – foto:** A Ana viu um vazamento de esgoto na frente da escola. Ela abre
  o Reclame Já e começa um novo reporte, anexando uma foto.
- **0:20 – local:** O GPS marca o local, e o app mostra o endereço com rua e
  número.
- **0:27 – descrição:** Depois, ela descreve o problema com as próprias palavras.
- **0:40 – categoria:** Ela não precisa saber qual secretaria cuida disso: deixa a
  inteligência artificial classificar.
- **0:45 – confirmação:** Ao enviar, recebe o protocolo. A IA lê o relato, define
  a categoria e a urgência e encaminha ao órgão responsável. A Ana confere e
  confirma.
- **0:55 – painel:** Na mesma hora, o reporte aparece no painel da prefeitura, com
  foto, localização e prazo.

## Cena 2: o órgão atende e resolve (1:05 – 1:45)

- **1:05 – órgão abre:** Agora, do lado da prefeitura: a equipe do órgão abre a
  ocorrência e vê tudo o que a cidadã enviou.
- **1:15 – em andamento:** Ao iniciar o atendimento, a equipe registra uma
  justificativa, e a Ana é avisada: no app, o status muda para "Em andamento".
- **1:30 – resolvido:** Com o serviço concluído, a equipe marca como resolvido. A
  cidadã acompanha cada etapa, com histórico e prazo, sem precisar ligar para
  ninguém.

## Cena 3: gestão pública com dados (1:45 – 2:20)

- **1:45 – painel de controle:** Para a gestão, o painel reúne os números da
  cidade: reportes abertos e concluídos, prazos vencidos, os temas mais
  frequentes e o desempenho de cada órgão.
- **2:05 – indicadores públicos:** E os indicadores ficam abertos à população,
  com tempo médio de resposta e taxa de resolução, sem expor dados pessoais, e
  podem ser exportados em CSV.

## Encerramento (2:20 – 2:28)

> Reclame Já: o cidadão relata, a IA encaminha e a cidade presta contas.

## Juntar a narração ao vídeo

1. Grave um arquivo por bloco e coloque em `gravacoes/<demo>/falas/`
   (`1.ogg` = cena 1, `2.ogg` = cena 2, `3.ogg` = cena 3, `4.ogg` = encerramento).
2. Em `falas/posicoes.json`, cada trecho recorta um pedaço da fala (`de`/`ate`, em
   segundos dentro do arquivo) e diz em que segundo do vídeo ele entra (`em`).
   Os cortes ficam nas pausas entre frases; os tempos de `em` saem dos quadros
   do vídeo (quando a galeria abre, quando o status muda no app etc.).
3. `python3 tests/e2e/narrar.py tests/e2e/gravacoes/<demo>` gera
   `00-demo-2min30-com-narracao.mp4` a partir de `00-demo-2min30-sem-narracao.mp4`
   (vídeo copiado sem reencode, voz em AAC 160 kbps com limitador em -1 dBFS).
