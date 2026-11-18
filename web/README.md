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

As telas administrativas usam dados ilustrativos. Autenticação institucional,
despachos, mudanças de status e notificações precisam ser conectados aos
serviços correspondentes antes de uso operacional.
