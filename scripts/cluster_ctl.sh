#!/usr/bin/env bash

ACTION="${1:-status}"

case "$ACTION" in
  start)
    echo "Stopping any existing cockroach processes..."
    pkill -9 -f cockroach 2>/dev/null || true
    sleep 1

    echo "Starting Node 1 (port 26257, http 8080)..."
    nohup cockroach start --insecure --store=type=mem,size=1GB \
      --listen-addr=127.0.0.1:26257 --http-addr=127.0.0.1:8080 \
      --join=127.0.0.1:26257,127.0.0.1:26258,127.0.0.1:26259 \
      </dev/null >/tmp/crdb_node1.log 2>&1 &

    echo "Starting Node 2 (port 26258, http 8081)..."
    nohup cockroach start --insecure --store=type=mem,size=1GB \
      --listen-addr=127.0.0.1:26258 --http-addr=127.0.0.1:8081 \
      --join=127.0.0.1:26257,127.0.0.1:26258,127.0.0.1:26259 \
      </dev/null >/tmp/crdb_node2.log 2>&1 &

    echo "Starting Node 3 (port 26259, http 8082)..."
    nohup cockroach start --insecure --store=type=mem,size=1GB \
      --listen-addr=127.0.0.1:26259 --http-addr=127.0.0.1:8082 \
      --join=127.0.0.1:26257,127.0.0.1:26258,127.0.0.1:26259 \
      </dev/null >/tmp/crdb_node3.log 2>&1 &

    echo "Initializing cluster on 127.0.0.1:26257..."
    cockroach init --insecure --host=127.0.0.1:26257
    sleep 2
    echo "Cluster initialized successfully!"
    cockroach node status --insecure --host=127.0.0.1:26257
    ;;

  stop)
    echo "Stopping CockroachDB cluster..."
    pkill -9 -f cockroach || true
    echo "Cluster stopped."
    ;;

  status)
    cockroach node status --insecure --host=127.0.0.1:26257
    ;;

  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
