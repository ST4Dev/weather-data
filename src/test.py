from time import time
from datetime import datetime, timezone
from utils.logger import get_logger, setup_logging
import openmeteo_requests
import requests_cache
from retry_requests import retry

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
        
        # Формирование результата
        weather_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
                "elevation": response.Elevation()
            },
            "current": {
                "time": datetime.fromtimestamp(current.Time(), timezone.utc).isoformat(),
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
        0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность",
        3: "Пасмурно", 45: "Туман", 48: "Изморозь",
        51: "Морось слабая", 53: "Морось умеренная", 55: "Морось сильная",
        61: "Дождь слабый", 63: "Дождь умеренный", 65: "Дождь сильный",
        71: "Снег слабый", 73: "Снег умеренный", 75: "Снег сильный",
        80: "Ливень слабый", 81: "Ливень умеренный", 82: "Ливень сильный",
        95: "Гроза", 96: "Гроза с градом слабая", 99: "Гроза с градом сильная"
    }
    
    weather_description = weather_codes.get(
        current['weather_code'], 
        f"Код погоды: {current['weather_code']}"
    )
    
    logger.info("СВОДКА ПОГОДЫ")
    logger.info(f"Время: {current['time'][11:19]} UTC")
    logger.info(f"Температура: {current['temperature']}°C (ощущается как {current['apparent_temperature']}°C)")
    logger.info(f"Влажность: {current['humidity']}%")
    logger.info(f"Погода: {weather_description}")
    logger.info(f"Ветер: {current['wind_speed']} км/ч, порывы до {current['wind_gusts']} км/ч")
    logger.info(f"Давление: {current['surface_pressure']} hPa")
    logger.info(f"Осадки: {current['precipitation']} мм/ч")

def main():
    # Настройка логирования
    setup_logging(
        log_file='weather-data.log',
        log_level=10,  # DEBUG
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
        # logger.debug(f"Полные данные: {weather_data}")
        
        # Здесь можно добавить сохранение в базу данных, файл и т.д.
        # save_to_database(weather_data)
        # save_to_json(weather_data, 'weather_data.json')
    else:
        logger.warning("Не удалось получить данные погоды")

if __name__ == '__main__':
    start_time = time()  # Время начала запуска скрипта
    main()
    logger.info(f'Скрипт выполнен за {(time() - start_time):.2f} с\n{"=" * 100}')