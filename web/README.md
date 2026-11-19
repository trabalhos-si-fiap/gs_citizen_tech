# Reclame Já Web

Aplicação administrativa Angular para servidores municipais: acesso
institucional, painel de controle, gestão de ocorrências e moderação. As telas
usam os tokens definidos em `src/theme.css`, alinhados à identidade visual de
`docs_tecnicas/DESIGN.md`.

## Executar

```bash
npm install
npm start
```

O servidor local abre em `http://localhost:4200`. O painel de indicadores
públicos fica disponível em `/indicadores`; ele consulta
`http://localhost:8000/v1/public/metrics` por padrão. Para apontar para outra
API, defina `window.RECLAME_JA_API_URL` antes de iniciar a aplicação.

O login (`/login`) é integrado à API: e-mail + código OTP de 6 dígitos, sessão
com refresh automático, guard de rotas e logout. Veja
`docs/documentacao/guia-teste-login-web.md`. Testes: `npm test`.

## Telas ligadas à API

| Rota | Perfis | API |
|---|---|---|
| `/dashboard` | todos | `GET /v1/staff/analytics` (7 dias, 30 dias ou 12 semanas), `GET /v1/staff/reports?overdue=true`; exporta CSV |
| `/ocorrencias` | todos | `GET /v1/staff/reports` (busca, status, categoria, atraso, paginação) e `GET /v1/staff/summary` |
| `/ocorrencias/:id` | todos | `GET /v1/staff/reports/{id}`; ações conforme o perfil (abaixo) |
| `/moderacao` | moderator, admin | `GET /v1/staff/moderation` |
| `/indicadores` | todos | `GET /v1/public/metrics` |

Ações no detalhe:

- **Status** (`agency`, só reportes do próprio órgão): iniciar atendimento com
  prazo, resolver ou contestar com justificativa.
- **Redirecionar** (`agency` no próprio escopo, `manager`, `admin`): escolhe o
  órgão de destino (`GET /v1/staff/agencies?scope=all`) e justifica.
- **Moderação** (`moderator`, `admin`): aprovar (com reclassificação opcional)
  ou rejeitar, sempre com justificativa.

Todas as chamadas passam por `src/app/staff-api.service.ts`, que converte os
erros da API em mensagens para a tela. A mensagem oficial ao cidadão (B5 do
plano de fechamento) ainda não existe na API, por isso não aparece no detalhe.
