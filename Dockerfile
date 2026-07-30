# battery-data : everything in one container, nothing installed on your machine.
#   docker compose up
FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pandas python3-numpy python3-yaml \
      python3-jsonschema python3-psycopg2 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
COPY . /repo

# Postgres runs everything in /docker-entrypoint-initdb.d on first start,
# in filename order, against the database named by POSTGRES_DB.
RUN set -eux; \
    mkdir -p /docker-entrypoint-initdb.d; \
    i=0; \
    for f in $(ls /repo/schema/*.sql | sort); do \
      i=$((i+1)); \
      cp "$f" "$(printf '/docker-entrypoint-initdb.d/%03d_%s' "$i" "$(basename "$f")")"; \
    done; \
    cp /repo/seed/001_reference_cells.sql /docker-entrypoint-initdb.d/900_seed.sql; \
    printf 'SELECT bd_graph.refresh();\n' > /docker-entrypoint-initdb.d/950_graph.sql

EXPOSE 5432 8080
