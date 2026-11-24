#!/bin/bash
# Prova de privilégio mínimo: tenta estragar o banco COM A CREDENCIAL DO APP.
# Tudo tem que dar "permission denied" / "must be owner". Rodar na VM, como root.
cd /opt/crepop/backend
APPURL=$(grep '^DATABASE_URL=' .env | cut -d= -f2- | sed 's/localhost/127.0.0.1/')
for sql in \
    "DROP TABLE pagina" \
    "DELETE FROM publicacao" \
    "UPDATE pagina SET conteudo_texto='x'" \
    "TRUNCATE registro_consulta" \
    "INSERT INTO publicacao (titulo) VALUES ('lixo')" \
    "CREATE TABLE lixo (x int)" \
    "DELETE FROM registro_consulta" \
    "ALTER TABLE usuario ADD COLUMN x int"; do
    printf '%-48s -> ' "$sql"
    docker exec -i crepop-pg psql "$APPURL" -v ON_ERROR_STOP=1 -c "$sql" 2>&1 | head -1
done

echo "--- pela web, sem login"
curl -s -o /dev/null -w "GET /            -> %{http_code}\n" http://127.0.0.1/
curl -s -o /dev/null -w "POST /buscar     -> %{http_code}\n" -X POST http://127.0.0.1/buscar -H 'Content-Type: application/json' -d '{"termo":"x"}'
curl -s -o /dev/null -w "GET /docs        -> %{http_code}\n" http://127.0.0.1/docs
curl -s -o /dev/null -w "POST /ingerir    -> %{http_code}\n" -X POST http://127.0.0.1/ingerir
