#!/bin/bash
set -e

echo "Building GhostWire binaries in Docker..."

cd "$(dirname "$0")/.."

echo "Building Docker image..."
docker build -t ghostwire-builder -f build/Dockerfile .

echo "Building binaries..."
docker run --rm -v "$(pwd):/build" ghostwire-builder bash -c "
cd /build
python -m PyInstaller --onefile --name ghostwire-server server.py
python -m PyInstaller --onefile --name ghostwire-client client.py
"

echo "Generating checksums..."
cd dist
sha256sum ghostwire-server > ghostwire-server.sha256
sha256sum ghostwire-client > ghostwire-client.sha256
cd ..

echo "Build complete!"
echo "Binaries available in dist/"
ls -lh dist/
