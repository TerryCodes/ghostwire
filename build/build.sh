#!/bin/bash
set -e

echo "Building GhostWire binaries..."

cd "$(dirname "$0")/.."

python3.13 -m PyInstaller --onefile --name ghostwire-server --add-data "frontend:frontend" server.py
python3.13 -m PyInstaller --onefile --name ghostwire-client client.py

echo "Generating checksums..."
cd dist
sha256sum ghostwire-server > ghostwire-server.sha256
sha256sum ghostwire-client > ghostwire-client.sha256
cd ..

echo "Build complete!"
echo "Binaries available in dist/"
ls -lh dist/
