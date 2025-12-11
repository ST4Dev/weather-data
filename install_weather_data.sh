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

# 1. Запрос имени пользователя
echo ""
echo "Введите имя пользователя, от которого будет работать сервис:"
read -p "Имя пользователя (по умолчанию: soultrader): " USER_INPUT

# Установка значения по умолчанию, если пользователь не ввел ничего
if [ -z "$USER_INPUT" ]; then
    USER="soultrader"
    log_info "Используется пользователь по умолчанию: $USER"
else
    USER="$USER_INPUT"
    log_info "Установлен пользователь: $USER"
fi

# Переменные
GROUP="adm"
PROJECT_DIR="/home/$USER/weather-data"
VENV_DIR="$PROJECT_DIR/venv"
REPO_URL="https://github.com/ST4Dev/weather-data.git"
SERVICE_FILE="/etc/systemd/system/weather-data.service"
TIMER_FILE="/etc/systemd/system/weather-data.timer"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"

# 2. Проверка существования пользователя
if ! id "$USER" &>/dev/null; then
    log_error "Пользователь $USER не существует!"
    echo ""
    echo "Хотите создать пользователя? (y/n): "
    read -p "Ваш выбор: " CREATE_USER
    
    if [[ "$CREATE_USER" =~ ^[Yy]$ ]]; then
        log_info "Создание пользователя $USER..."
        
        # Создаем пользователя
        adduser --gecos "" "$USER"
        
        # Добавляем пользователя в группу adm для доступа к логам
        usermod -aG adm "$USER"
        
        # Добавляем пользователя в группу sudo
        usermod -aG sudo "$USER"
        
        # Настройка sudo без пароля для текущего пользователя (опционально)
        echo "Хотите настроить sudo без пароля для пользователя $USER? (y/n): "
        read -p "Ваш выбор: " SUDO_NOPASSWD
        
        if [[ "$SUDO_NOPASSWD" =~ ^[Yy]$ ]]; then
            log_info "Настройка sudo без пароля..."
            echo "$USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USER
            chmod 0440 /etc/sudoers.d/$USER
            log_success "Настроен sudo без пароля для пользователя $USER"
        fi
        
        log_success "Пользователь $USER создан и добавлен в группы adm и sudo"
    else
        log_error "Установка прервана. Создайте пользователя $USER вручную и запустите скрипт снова."
        exit 1
    fi
else
    # Проверяем, есть ли пользователь в группе sudo
    if ! groups "$USER" | grep -q "\bsudo\b"; then
        log_info "Пользователь $USER существует, но не входит в группу sudo"
        echo ""
        echo "Хотите добавить пользователя $USER в группу sudo? (y/n): "
        read -p "Ваш выбор: " ADD_TO_SUDO
        
        if [[ "$ADD_TO_SUDO" =~ ^[Yy]$ ]]; then
            usermod -aG sudo "$USER"
            log_success "Пользователь $USER добавлен в группу sudo"
        else
            log_info "Пользователь $USER не добавлен в группу sudo (ограниченные права)"
        fi
    else
        log_success "Пользователь $USER уже входит в группу sudo"
    fi
    
    # Проверяем, есть ли пользователь в группе adm
    if ! groups "$USER" | grep -q "\badm\b"; then
        log_info "Добавляем пользователя $USER в группу adm..."
        usermod -aG adm "$USER"
        log_success "Пользователь $USER добавлен в группу adm"
    fi
fi

# 3. Обновление системы и установка зависимостей
log_info "Обновление системы и установка зависимостей..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git

# 4. Клонирование или обновление репозитория
log_info "Работа с репозиторием..."
if [ -d "$PROJECT_DIR" ]; then
    log_info "Директория уже существует, обновляем..."
    cd "$PROJECT_DIR"
    git pull origin main || log_info "Не удалось обновить, продолжаем с текущей версией"
else
    log_info "Клонирование репозитория..."
    sudo -u "$USER" git clone "$REPO_URL" "$PROJECT_DIR"
fi

# 5. Создание виртуального окружения
log_info "Настройка виртуального окружения..."
if [ ! -d "$VENV_DIR" ]; then
    sudo -u "$USER" python3 -m venv "$VENV_DIR"
fi

# 6. Установка Python зависимостей
log_info "Установка зависимостей Python..."

# Переходим в директорию проекта
cd "$PROJECT_DIR"

# Проверяем существование requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    log_error "Файл requirements.txt не найден в $PROJECT_DIR"
    echo "Содержимое директории $PROJECT_DIR:"
    ls -la "$PROJECT_DIR"
    exit 1
fi

log_info "Найден файл requirements.txt, устанавливаем зависимости..."

# Устанавливаем зависимости из requirements.txt
sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install --upgrade pip"
sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install -r '$REQUIREMENTS_FILE'"

# Альтернативная установка, если requirements.txt пустой или содержит только основные пакеты
# sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install openmeteo-requests requests-cache retry-requests pytz"

# 7. Настройка прав доступа
log_info "Настройка прав доступа..."
chown -R "$USER:$GROUP" "$PROJECT_DIR"
find "$PROJECT_DIR" -type f -name "*.py" -exec chmod 755 {} \;

# 8. Создание файлов systemd
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
Description=Run weather data collection every 15 minutes
Requires=weather-data.service

[Timer]
# Каждые 15 минут
OnCalendar=*:0/15

# Каждые 10 минут
# OnCalendar=*:0/10

# Каждый час в 00 минут
# OnCalendar=hourly

# Каждые 30 минут
# OnCalendar=*:0/30

# В определенное время (например, каждые 3 часа)
# OnCalendar=00:00,03:00,06:00,09:00,12:00,15:00,18:00,21:00

Persistent=true
RandomizedDelaySec=30

[Install]
WantedBy=timers.target
EOF

# 9. Настройка systemd
log_info "Настройка systemd..."
systemctl daemon-reload
systemctl enable weather-data.timer
systemctl start weather-data.timer

# 10. Запуск тестового выполнения
log_info "Тестовый запуск сервиса..."
systemctl start weather-data.service
sleep 2

# 11. Проверка установки
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

# 12. Вывод информации
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
echo "Расписание: сбор данных каждые 15 минут"
echo "=========================================="

# 13. Первоначальный запуск
log_info "Выполняю первоначальный запуск для проверки..."
cd "$PROJECT_DIR"
sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && python ./src/weather_data.py"

log_success "Установка завершена успешно!"