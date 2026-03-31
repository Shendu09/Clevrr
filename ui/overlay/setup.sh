#!/bin/bash
# Install Electron overlay dependencies

set -e

echo "=========================================="
echo "  Installing Clevrr Overlay Dependencies"
echo "=========================================="

cd ui/overlay

echo ""
echo "[1/3] Checking for Node.js..."
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed"
    echo "Install from https://nodejs.org/"
    exit 1
fi
node --version

echo ""
echo "[2/3] Installing npm packages..."
npm install

echo ""
echo "[3/3] Verifying Electron..."
npx electron --version

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "To launch Clevrr with Electron overlay:"
echo "  python main.py --ui overlay"
echo ""
