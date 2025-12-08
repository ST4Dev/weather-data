import logging
from pathlib import Path
from typing import Optional

# Список логгеров сторонних библиотек, которые нужно отключить или ограничить
THIRD_PARTY_LOGGERS = [
    'matplotlib',
    'PIL',
    'urllib3',
    'requests_cache'
]

# Словарь для преобразования числовых уровней в текстовые
LOG_LEVEL_NAMES = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO", 
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}

def get_logger(name: str = 'test-name') -> logging.Logger:
    """Возвращает настроенный логгер"""
    return logging.getLogger(name)

def get_log_level_name(log_level: str | int) -> str:
    """Возвращает человеко-читаемое имя уровня логирования
    
    Args:
        log_level: Уровень логирования (число или строка)
        
    Returns:
        Строковое представление уровня логирования
    """
    if isinstance(log_level, str):
        # Если передана строка, проверяем есть ли такое имя
        log_level_upper = log_level.upper()
        if hasattr(logging, log_level_upper):
            return log_level_upper
        return log_level.upper()
    else:
        # Если передано число, ищем в словаре
        return LOG_LEVEL_NAMES.get(log_level, f"UNKNOWN({log_level})")

def setup_logging(
    log_file: Optional[str] = 'test_name.log',
    log_level: str | int = logging.DEBUG,  # DEBUG = 10, INFO = 20, WARNING = 30, ERROR = 40, CRITICAL = 50, либо строка!
    console: bool = False,
    logger_name: str = 'Logger',
    suppress_third_party: bool = True,
    enable_file_logging: bool = True  # Новая опция для включения/отключения файлового логирования
) -> None:
    """Настраивает логирование
    
    Args:
        log_file: Путь к файлу логов. Если None, файл не создается.
        log_level: Уровень логирования (по умолчанию DEBUG).
        console: Выводить логи в консоль.
        logger_name: Имя основного логгера.
        suppress_third_party: Отключать логи сторонних библиотек.
        enable_file_logging: Включить логирование в файл. Если False, файловый логгер не создается.
    """
    logger = get_logger(logger_name)
    
    # Очищаем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    handlers = []
    
    # Добавляем файловый обработчик только если включено файловое логирование
    if enable_file_logging and log_file:
        # Создаем директорию для логов, если ее нет
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    
    if console:
        handlers.append(logging.StreamHandler())
    
    if not handlers:
        handlers.append(logging.NullHandler())
    
    # Преобразуем строковый уровень в числовой, если нужно
    if isinstance(log_level, str):
        log_level_value = getattr(logging, log_level.upper(), logging.DEBUG)
    else:
        log_level_value = log_level
    
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%d.%m.%Y %H:%M:%S',
        level=log_level_value,
        handlers=handlers
    )
    
    # Настройка логгеров сторонних библиотек
    if suppress_third_party:
        for lib_name in THIRD_PARTY_LOGGERS:
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.WARNING)  # Показывать только WARNING и выше
            lib_logger.propagate = True  # Позволяет родительским логгерам обрабатывать сообщения
    
    # Получаем человеко-читаемое имя уровня логирования
    log_level_name = get_log_level_name(log_level)
    
    logger.debug("Логирование инициализировано")
    logger.debug(f"Уровень логирования: {log_level_name}")
    logger.debug(f"Файловое логирование: {'включено' if enable_file_logging else 'отключено'}")