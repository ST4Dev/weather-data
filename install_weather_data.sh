#!/bin/bash

# Скрипт автоматической установки weather-data для Ubuntu
# Запуск: sudo bash install_weather_data.sh

set -e  # Прерывать выполнение при ошибках

echo "=========================================="
echo " Установка сервиса Weather Data Collection"
echo "=========================================="

# Проверка прав
if [ "$EUID" -ne 0 ]; then 
    echo "Ошибка: Скрипт должен запускаться с правами root (sudo)"
    exit 1
fi

# Переменные
USER="soultrader"
GROUP="adm"
PROJECT_DIR="/home/$USER/weather-data"
VENV_DIR="$PROJECT_DIR/venv"
REPO_URL="https://github.com/ST4Dev/weather-data.git"
SERVICE_FILE="/etc/systemd/system/weather-data.service"
TIMER_FILE="/etc/systemd/system/weather-data.timer"

# Функция для вывода сообщений
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_success() {
    echo "[SUCCESS] $1"
}

# 1. Обновление системы и установка зависимостей
log_info "Обновление системы и установка зависимостей..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git

# 2. Проверка существования пользователя
if ! id "$USER" &>/dev/null; then
    log_error "Пользователь $USER не существует!"
    exit 1
fi

# 3. Клонирование или обновление репозитория
log_info "Работа с репозиторием..."
if [ -d "$PROJECT_DIR" ]; then
    log_info "Директория уже существует, обновляем..."
    cd "$PROJECT_DIR"
    git pull origin main || log_info "Не удалось обновить, продолжаем с текущей версией"
else
    log_info "Клонирование репозитория..."
    sudo -u "$USER" git clone "$REPO_URL" "$PROJECT_DIR"
fi

# 4. Создание виртуального окружения
log_info "Настройка виртуального окружения..."
if [ ! -d "$VENV_DIR" ]; then
    sudo -u "$USER" python3 -m venv "$VENV_DIR"
fi

# 5. Установка Python зависимостей
log_info "Установка зависимостей Python..."
sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install --upgrade pip"
sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install -r requirements.txt"
# sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install openmeteo-requests requests-cache retry-requests pytz"

# 6. Настройка прав доступа
log_info "Настройка прав доступа..."
chown -R "$USER:$GROUP" "$PROJECT_DIR"
find "$PROJECT_DIR" -type f -name "*.py" -exec chmod 755 {} \;

# 7. Создание файлов systemd
log_info "Создание systemd сервиса..."

# Сервисный файл
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Weather Data Collection Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$GROUP
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/src/weather_data.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Настройки безопасности
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$PROJECT_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Таймер
cat > "$TIMER_FILE" << EOF
[Unit]
Description=Run weather data collection every 5 minutes
Requires=weather-data.service

[Timer]
OnCalendar=*:0/5
Persistent=true
RandomizedDelaySec=30

[Install]
WantedBy=timers.target
EOF

# 8. Настройка systemd
log_info "Настройка systemd..."
systemctl daemon-reload
systemctl enable weather-data.timer
systemctl start weather-data.timer

# 9. Запуск тестового выполнения
log_info "Тестовый запуск сервиса..."
systemctl start weather-data.service
sleep 2

# 10. Проверка установки
log_info "Проверка установки..."

# Проверка сервиса
if systemctl is-active --quiet weather-data.service; then
    log_success "Сервис успешно запущен"
else
    log_error "Сервис не запущен"
    journalctl -u weather-data.service --no-pager -n 13
fi

# Проверка таймера
if systemctl is-active --quiet weather-data.timer; then
    log_success "Таймер успешно запущен"
else
    log_error "Таймер не запущен"
fi

# Проверка логов
if [ -f "$PROJECT_DIR/weather-data.log" ]; then
    log_success "Файл логов создан"
    echo "Последние строки лога:"
    tail -13 "$PROJECT_DIR/weather-data.log"
else
    log_info "Файл логов еще не создан (первый запуск может быть в процессе)"
fi

# 11. Вывод информации
echo ""
echo "=========================================="
echo " Установка завершена!"
echo "=========================================="
echo ""
echo "Команды для управления:"
echo "  Просмотр статуса:    sudo systemctl status weather-data.service"
echo "  Просмотр логов:      sudo journalctl -u weather-data.service -f"
echo "  Просмотр таймеров:   systemctl list-timers --all"
echo "  Остановка сервиса:   sudo systemctl stop weather-data.service"
echo "  Запуск сервиса:      sudo systemctl start weather-data.service"
echo "  Перезагрузка:        sudo systemctl restart weather-data.service"
echo ""
echo "Файлы:"
echo "  Директория проекта:  $PROJECT_DIR"
echo "  Логи приложения:     $PROJECT_DIR/weather-data.log"
echo "  Кэш API:             $PROJECT_DIR/.cache/"
echo "  Сервис systemd:      $SERVICE_FILE"
echo "  Таймер systemd:      $TIMER_FILE"
echo ""
echo "Расписание: сбор данных каждые 5 минут"
echo "=========================================="

# 12. Первоначальный запуск
log_info "Выполняю первоначальный запуск для проверки..."
sudo -u "$USER" bash -c "cd $PROJECT_DIR && source $VENV_DIR/bin/activate && python weather_data.py"

log_success "Установка завершена успешно!"