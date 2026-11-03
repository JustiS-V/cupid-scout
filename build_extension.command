#!/bin/bash
# Локальная сборка ZIP-пакета расширения для отправки друзьям
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VERSION=$(grep -o '"version": "[^"]*"' extension/manifest.json | cut -d'"' -f4)
mkdir -p dist
ZIP_NAME="cupid-scout-extension-v${VERSION}.zip"

echo "========================================================"
echo "📦 Сборка Cupid Scout Extension v${VERSION}..."
echo "========================================================"

cd extension
zip -r "../dist/${ZIP_NAME}" . -x "*.DS_Store" "*__pycache__*"
cd ..

shasum -a 256 "dist/${ZIP_NAME}" > "dist/checksums.txt"

echo ""
echo "🎉 Сборка завершена успешно!"
echo "📁 Архив готов для друзей: dist/${ZIP_NAME}"
echo "========================================================"
open dist
