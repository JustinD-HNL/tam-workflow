#!/bin/bash
set -e

echo "Starting TAM Workflow..."

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker Desktop and try again."
  exit 1
fi

# Start services (no rebuild, preserves DB volume)
docker compose up -d

# Wait for backend to be healthy
echo "Waiting for backend..."
for i in $(seq 1 20); do
  if curl -s http://localhost:8001/healthz > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo ""
echo "TAM Workflow is running:"
echo "  Frontend:  http://localhost:3001"
echo "  Backend:   http://localhost:8001"
echo "  API docs:  http://localhost:8001/docs"
echo ""
echo "To stop:    docker compose stop"
echo "To restart: docker compose restart"
echo "To view logs: docker compose logs -f backend"
