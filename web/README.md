# Reclame Já Web

Aplicação administrativa Angular com protótipos navegáveis de acesso
institucional, painel de zeladoria, triagem e gestão de ocorrências. As telas
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

As demais telas administrativas usam dados ilustrativos. Despachos, mudanças de status e notificações precisam ser conectados aos
serviços correspondentes antes de uso operacional.
