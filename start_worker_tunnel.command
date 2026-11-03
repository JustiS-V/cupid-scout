#!/bin/bash
# Скрипт для проброса порта LM Studio (1234) с Windows-воркера на этот Mac
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KNOWN_HOSTS="/Users/val9/Desktop/Capitolium_/.runtime/worker-vision-known-hosts"

echo "========================================================"
echo "🏹 Dating AI: Запуск SSH-туннеля к 12-ядерному воркеру..."
echo "========================================================"

# Проверяем, не открыт ли уже порт 1234
if lsof -Pi :1234 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Порт 1234 уже слушается (туннель или локальный LM Studio активен)."
    exit 0
fi

# Пробуем через локальный Wi-Fi (быстрее), затем через Tailscale
echo "Подключение к воркеру (192.168.31.160 / 100.108.136.100)..."
ssh -o UserKnownHostsFile="$KNOWN_HOSTS" -o HostKeyAlias=100.108.136.100 -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=4 -f -N -L 1234:127.0.0.1:1234 valentyn@192.168.31.160 2>/dev/null \
|| ssh -o UserKnownHostsFile="$KNOWN_HOSTS" -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=6 -f -N -L 1234:127.0.0.1:1234 valentyn@100.108.136.100 2>/dev/null

if lsof -Pi :1234 -sTCP:LISTEN -t >/dev/null ; then
    echo "🎉 Туннель успешно запущен! http://127.0.0.1:1234 подключен к media-vision воркера."
else
    echo "❌ Ошибка: не удалось поднять туннель к воркеру. Проверьте Tailscale/Wi-Fi."
fi
