#!/bin/bash
# Запуск Google Chrome с открытым портом отладки 9222 для AI-дейтинг агента
PROFILE_DIR="$HOME/.dating_chrome_profile"
mkdir -p "$PROFILE_DIR"

echo "========================================================"
echo "🌐 Запуск Google Chrome для AI Dating Agent (порт 9222)..."
echo "========================================================"
echo "Профиль сохраняется в: $PROFILE_DIR (все логины останутся сохранены)"

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR" \
  "https://tinder.com" &

echo "✅ Chrome запущен! Войдите в свои аккаунты дейтингов."
