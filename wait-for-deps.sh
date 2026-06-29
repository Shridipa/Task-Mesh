#!/bin/sh
# Wait for PostgreSQL and Redis to be reachable before starting the app
set -e
host=${POSTGRES_HOST:-postgres}
port=${POSTGRES_PORT:-5432}
redis_host=${REDIS_HOST:-redis}
redis_port=${REDIS_PORT:-6379}

until nc -z $host $port; do
  echo "Waiting for PostgreSQL at $host:$port..."
  sleep 1
done

until nc -z $redis_host $redis_port; do
  echo "Waiting for Redis at $redis_host:$redis_port..."
  sleep 1
done

exec "$@"
