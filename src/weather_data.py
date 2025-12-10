from time import time
from datetime import datetime, timezone
from utils.logger import get_logger, setup_logging
import openmeteo_requests
import requests_cache
from retry_requests import retry
import pytz

logger = get_logger('Weather-data')

# Настройка клиента Open-Meteo с кэшированием и повторными попытками
def setup_openmeteo_client(cache_expire_seconds=300):
    """
    Настраивает клиент Open-Meteo с кэшированием и повторными попытками
    
    Args:
        cache_expire_seconds: Время жизни кэша в секундах (по умолчанию 5 минут)
    
    Returns:
        Настроенный клиент Open-Meteo
    """
    # Настройка кэширования сессии
    cache_session = requests_cache.CachedSession(
        '.cache', 
        expire_after=cache_expire_seconds
    )
    
    # Настройка повторных попыток
    retry_session = retry(
        cache_session, 
        retries=3, 
        backoff_factor=0.5
    )
    
    # Создание клиента Open-Meteo
    return openmeteo_requests.Client(session=retry_session)

# Функция для конвертации времени из UTC в МСК с использованием pytz
def convert_utc_to_msk_pytz(utc_datetime_str):
    """
    Конвертирует строку времени из UTC в МСК с использованием pytz
    
    Args:
        utc_datetime_str: Строка времени в формате ISO (YYYY-MM-DDTHH:MM:SS+00:00)
    
    Returns:
        Строка времени в МСК в формате YYYY-MM-DD HH:MM:SS
    """
    try:
        # Определяем часовые пояса
        utc_tz = pytz.UTC
        msk_tz = pytz.timezone('Europe/Moscow')
        
        # Парсим строку UTC
        if '+' in utc_datetime_str or 'Z' in utc_datetime_str:
            # Если есть информация о часовом поясе
            naive_dt = datetime.fromisoformat(utc_datetime_str.replace('Z', '+00:00'))
            utc_dt = naive_dt.astimezone(utc_tz) if naive_dt.tzinfo is None else naive_dt
        else:
            # Если нет информации о часовом поясе, считаем что это UTC
            naive_dt = datetime.fromisoformat(utc_datetime_str)
            utc_dt = utc_tz.localize(naive_dt)
        
        # Конвертируем в МСК
        msk_dt = utc_dt.astimezone(msk_tz)
        
        # Форматируем для удобного отображения
        return msk_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Ошибка конвертации времени с pytz: {str(e)}")
        return utc_datetime_str

# Альтернативная функция с простым подходом
def get_current_msk_time():
    """Получает текущее время в МСК"""
    msk_tz = pytz.timezone('Europe/Moscow')
    msk_time = datetime.now(msk_tz)
    return msk_time.strftime('%Y-%m-%d %H:%M:%S')

# Функция запроса погоды
def get_weather_data(client, latitude, longitude, forecast_days=7):
    """
    Получает данные погоды для указанных координат
    
    Args:
        client: Клиент Open-Meteo
        latitude: Широта
        longitude: Долгота
        forecast_days: Количество дней прогноза (макс. 16)
    
    Returns:
        Словарь с данными погоды или None в случае ошибки
    """
    url = "https://api.open-meteo.com/v1/forecast"
    
    # Параметры запроса
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": [
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "rain", "showers", "snowfall", "weather_code",
            "cloud_cover", "pressure_msl", "surface_pressure", "wind_speed_10m",
            "wind_direction_10m", "wind_gusts_10m"
        ],
        "hourly": [
            "temperature_2m", "relative_humidity_2m", "precipitation",
            "weather_code", "surface_pressure", "wind_speed_10m"
        ],
        "daily": [
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max", "apparent_temperature_min",
            "precipitation_sum", "precipitation_hours", "wind_speed_10m_max"
        ],
        "timezone": "auto",
        "forecast_days": forecast_days,
        "past_days": 0
    }
    
    try:
        logger.info(f"Запрос погоды для координат: {latitude}, {longitude}")
        
        # Выполнение запроса
        responses = client.weather_api(url, params=params)
        
        if not responses:
            logger.error("Получен пустой ответ от API")
            return None
        
        response = responses[0]
        
        # Извлечение данных
        current = response.Current()
        hourly = response.Hourly()
        daily = response.Daily()
        
        # Получаем время в UTC
        utc_time = datetime.fromtimestamp(current.Time(), timezone.utc)
        utc_time_str = utc_time.isoformat()
        
        # Конвертируем в МСК с использованием pytz
        msk_time_str = convert_utc_to_msk_pytz(utc_time_str)
        
        # Получаем текущее время выполнения скрипта в МСК
        current_msk_time = get_current_msk_time()
        
        # Формирование результата
        weather_data = {
            "timestamp": current_msk_time,  # Время получения данных в МСК
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),  # Для справки
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
                "elevation": response.Elevation()
            },
            "current": {
                "time_utc": utc_time_str,
                "time_msk": msk_time_str,  # Время наблюдения в МСК
                "temperature": round(current.Variables(0).Value(), 1),
                "humidity": round(current.Variables(1).Value()),
                "apparent_temperature": round(current.Variables(2).Value(), 1),
                "precipitation": round(current.Variables(3).Value(), 1),
                "rain": round(current.Variables(4).Value(), 1),
                "showers": round(current.Variables(5).Value(), 1),
                "snowfall": round(current.Variables(6).Value(), 1),
                "weather_code": int(current.Variables(7).Value()),
                "cloud_cover": round(current.Variables(8).Value()),
                "pressure_msl": round(current.Variables(9).Value()),
                "surface_pressure": round(current.Variables(10).Value()),
                "wind_speed": round(current.Variables(11).Value(), 1),
                "wind_direction": round(current.Variables(12).Value()),
                "wind_gusts": round(current.Variables(13).Value(), 1)
            },
            "forecast_days": forecast_days,
            "units": {
                "temperature": "°C",
                "precipitation": "mm",
                "pressure": "hPa",
                "wind_speed": "km/h"
            }
        }
        
        logger.info(f"Данные погоды успешно получены.")
        return weather_data
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных погоды: {str(e)}", exc_info=True)
        return None

# Функция для логирования сводной информации о погоде
def log_weather_summary(weather_data):
    """Логирует сводную информацию о текущей погоде"""
    if not weather_data:
        return
    
    current = weather_data['current']
    
    # Преобразование кода погоды в текстовое описание
    weather_codes = {
        0: "☀️ Ясно",
        1: "🌤️ Преимущественно ясно", 
        2: "⛅ Переменная облачность",
        3: "☁️ Пасмурно",
        45: "🌫️ Туман",
        48: "🌫️ Изморозь",
        51: "🌧️ Морось слабая",
        53: "🌧️ Морось умеренная",
        55: "🌧️ Морось сильная",
        56: "🌧️❄️ Ледяная морось слабая",
        57: "🌧️❄️ Ледяная морось сильная",
        61: "🌧️ Дождь слабый",
        63: "🌧️ Дождь умеренный",
        65: "🌧️ Дождь сильный",
        66: "🌧️🧊 Ледяной дождь слабый",
        67: "🌧️🧊 Ледяной дождь сильный",
        71: "🌨️ Снег слабый",
        73: "🌨️ Снег умеренный",
        75: "🌨️ Снег сильный",
        77: "❄️ Снежные зерна",
        80: "🌦️ Ливень слабый",
        81: "🌦️ Ливень умеренный",
        82: "⛈️ Ливень сильный",
        85: "🌨️ Снегопад слабый",
        86: "🌨️ Снегопад сильный",
        95: "⛈️ Гроза",
        96: "⛈️ Гроза с градом слабая",
        99: "⛈️ Гроза с градом сильная"
    }
    
    weather_description = weather_codes.get(
        current['weather_code'], 
        f"Код погоды: {current['weather_code']}"
    )

    logger.info("СВОДКА ПОГОДЫ")
    logger.info(f"Время наблюдения (МСК): {current['time_msk']}")
    logger.info(f"Время запроса (МСК):    {weather_data['timestamp']}")
    logger.info(f"Температура:            {current['temperature']}°C (ощущается как {current['apparent_temperature']}°C)")
    logger.info(f"Влажность:              {current['humidity']}%")
    logger.info(f"Погода:                 {weather_description}")
    logger.info(f"Ветер:                  {current['wind_speed']} км/ч, порывы до {current['wind_gusts']} км/ч")
    logger.info(f"Давление:               {current['surface_pressure']} hPa")
    logger.info(f"Осадки:                 {current['precipitation']} мм/ч")

def main():
    # Настройка логирования
    setup_logging(
        log_file='weather-data.log',
        log_level=20,  # INFO
        console=True, 
        suppress_third_party=True,
        enable_file_logging=True
    )
    
    # Координаты (пример: Белгород, Россия)
    latitude = 50.36
    longitude = 36.36
    
    # Настройка клиента Open-Meteo
    try:
        client = setup_openmeteo_client(cache_expire_seconds=300)
        logger.debug("Клиент Open-Meteo успешно настроен")
    except Exception as e:
        logger.error(f"Ошибка настройки клиента Open-Meteo: {str(e)}")
        return
    
    # Получение данных погоды
    weather_data = get_weather_data(
        client=client,
        latitude=latitude,
        longitude=longitude,
        forecast_days=3  # Получаем прогноз на 3 дня
    )
    
    # Логирование результата
    if weather_data:
        log_weather_summary(weather_data)
        
        # Дополнительная информация для отладки
        logger.debug(f"Полные данные: {weather_data}")

    else:
        logger.warning("Не удалось получить данные погоды")

if __name__ == '__main__':
    start_time = time()  # Время начала запуска скрипта
    logger.info(f"Скрипт запущен в {get_current_msk_time()} (МСК)")
    main()
    
    # Получаем время окончания в МСК
    msk_tz = pytz.timezone('Europe/Moscow')
    end_time_msk = datetime.now(msk_tz).strftime('%Y-%m-%d %H:%M:%S')
    
    logger.info(f'Скрипт выполнен в {end_time_msk} (МСК) за {(time() - start_time):.2f} секунд \n{'=' * 110}')