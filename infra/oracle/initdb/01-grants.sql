-- Executado pelo container Oracle apenas na primeira inicialização.
-- O usuário da aplicação (APP_USER) precisa agendar o job JOB_ATRASADOS.
ALTER SESSION SET CONTAINER = FREEPDB1;
GRANT CREATE JOB TO reclameja;
