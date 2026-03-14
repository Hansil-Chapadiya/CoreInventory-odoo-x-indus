#!/bin/bash
# Quick test of UOM creation endpoint

echo "Starting backend..."
cd "d:/OdooxIndus/backend"

# Start server in background
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
SERVER_PID=$!

echo "Waiting for server to start..."
sleep 3

echo ""
echo "=== Testing UOM Endpoints ==="
echo ""

# Get existing UOMs
echo "1. GET existing UOMs:"
curl -s http://localhost:8000/api/v1/products/uom/ | python -m json.tool | head -20
echo ""

# Create a new UOM
echo "2. POST - Create new UOM (Ton):"
curl -s -X POST http://localhost:8000/api/v1/products/uom/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Ton", "symbol": "ton"}' | python -m json.tool
echo ""

# Create another UOM
echo "3. POST - Create new UOM (Gallon):"
curl -s -X POST http://localhost:8000/api/v1/products/uom/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Gallon", "symbol": "gal"}' | python -m json.tool
echo ""

# Stop server
echo "Stopping server..."
kill $SERVER_PID
