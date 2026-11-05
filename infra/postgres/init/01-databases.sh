#!/bin/sh
# One database and one login per service. Safe to run any number of times:
# creates what's missing and keeps each login's password in step with .env.
#
# Runs (1) automatically on the first start of an empty data volume, and
# (2) on every `docker compose up` through the one-off db-setup container, so a
# service added later gets its database on an existing server too.
# To add a service: add one line to SERVICES below and its password to .env.
set -e
SERVICES="
auth:AUTH_DB_PASSWORD
audit:AUDIT_DB_PASSWORD
academics:ACADEMICS_DB_PASSWORD
content:CONTENT_DB_PASSWORD
events:EVENTS_DB_PASSWORD
eca:ECA_DB_PASSWORD
notify:NOTIFY_DB_PASSWORD
admissions:ADMISSIONS_DB_PASSWORD
careers:CAREERS_DB_PASSWORD
alumni:ALUMNI_DB_PASSWORD
search:SEARCH_DB_PASSWORD
"
for pair in $SERVICES; do
  name="${pair%%:*}"; var="${pair#*:}"
  password=$(eval "printf '%s' \"\${$var:-}\"")
  if [ -z "$password" ]; then echo "db-setup: $var is not set; skipping ncit_$name" >&2; continue; fi
  psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" -v role="ncit_$name" -v pw="$password" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'role') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role')\gexec
ALTER ROLE :"role" WITH LOGIN PASSWORD :'pw';
SELECT format('CREATE DATABASE %I OWNER %I', :'role', :'role') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'role')\gexec
SQL
  echo "db-setup: ncit_$name ready"
done
