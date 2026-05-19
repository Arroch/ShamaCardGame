#!/bin/bash
# Установка systemd-сервиса для Shama Bot.
# Запускать от root или через sudo: sudo bash deploy/install.sh

set -e

SERVICE_NAME="shama-bot"
SERVICE_FILE="$(dirname "$0")/${SERVICE_NAME}.service"
DEST="/etc/systemd/system/${SERVICE_NAME}.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Файл $SERVICE_FILE не найден"
    exit 1
fi

echo "Копируем $SERVICE_FILE → $DEST"
cp "$SERVICE_FILE" "$DEST"

echo "Перезагружаем systemd и включаем сервис..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "Готово. Команды управления:"
echo "  systemctl status $SERVICE_NAME"
echo "  systemctl restart $SERVICE_NAME"
echo "  systemctl stop $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
