#!/bin/bash
set -e

echo "Building GhostWire binaries in Docker..."

cd "$(dirname "$0")/.."

echo "Building Docker image..."
BUILD_ARGS=""
if [ -n "${HTTP_PROXY:-}" ]; then
  BUILD_ARGS="$BUILD_ARGS --build-arg HTTP_PROXY=$HTTP_PROXY"
fi
if [ -n "${HTTPS_PROXY:-}" ]; then
  BUILD_ARGS="$BUILD_ARGS --build-arg HTTPS_PROXY=$HTTPS_PROXY"
fi
docker build $BUILD_ARGS -t ghostwire-builder -f build/Dockerfile .

echo "Building binaries..."
docker run --rm -v "$(pwd):/build" ghostwire-builder bash -c "
cd /build
python3.13 -m PyInstaller --onefile --name ghostwire-server --add-data 'frontend:frontend' server.py
python3.13 -m PyInstaller --onefile --name ghostwire-client client.py
"

echo "Generating checksums..."
cd dist
sha256sum ghostwire-server > ghostwire-server.sha256
sha256sum ghostwire-client > ghostwire-client.sha256
cd ..

echo "Build complete!"
echo "Binaries available in dist/"
ls -lh dist/
