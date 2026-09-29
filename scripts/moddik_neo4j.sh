#!/usr/bin/env bash
# Project-local Neo4j for the Moddik demo projection. Uses the already-present neo4j:5.26 image (no download).
# The password is generated locally into a gitignored credentials file (.local/) and is never printed. The database is a
# REBUILDABLE projection: deleting this container loses no canonical evidence (canonical = runs/*.jsonl + provenance/).
set -euo pipefail
cd "$(dirname "$0")/.."
CRED=.local/moddik-neo4j.credentials
NAME=agent-foundry-moddik-neo4j
BOLT=7691; HTTP=7476
pw() { sed -n 's/^NEO4J_PASSWORD=//p' "$CRED"; }
case "${1:-up}" in
  up)
    if [ ! -f "$CRED" ]; then
      mkdir -p .local; umask 077
      printf 'NEO4J_URI=bolt://127.0.0.1:%s\nNEO4J_USER=neo4j\nNEO4J_PASSWORD=%s\n' "$BOLT" "$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" > "$CRED"
    fi
    if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then docker start "$NAME" >/dev/null; else
      docker run -d --name "$NAME" -p 127.0.0.1:$BOLT:7687 -p 127.0.0.1:$HTTP:7474 \
        -e NEO4J_AUTH="neo4j/$(pw)" -e NEO4J_server_memory_heap_initial__size=256m -e NEO4J_server_memory_heap_max__size=512m \
        -e NEO4J_server_memory_pagecache_size=128m neo4j:5.26 >/dev/null
    fi
    for i in $(seq 1 60); do
      if docker exec "$NAME" cypher-shell -u neo4j -p "$(pw)" "RETURN 1" >/dev/null 2>&1; then
        echo "NEO4J=READY uri=bolt://127.0.0.1:$BOLT credentials=PRESENT (VALUE=NOT_CAPTURED)"; exit 0; fi
      sleep 2
    done
    echo "NEO4J=NOT_READY (timeout)"; exit 1 ;;
  down) docker rm -f "$NAME" >/dev/null && echo "NEO4J=REMOVED (projection only; canonical evidence untouched)" ;;
  *) echo "usage: $0 [up|down]"; exit 2 ;;
esac
