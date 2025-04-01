import requests
import logging
import os
import time
import sys
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка наличия обязательных переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        missing_tokens = []
        if not PRACTICUM_TOKEN:
            missing_tokens.append('PRACTICUM_TOKEN')
        if not TELEGRAM_TOKEN:
            missing_tokens.append('TELEGRAM_TOKEN')
        if not TELEGRAM_CHAT_ID:
            missing_tokens.append('TELEGRAM_CHAT_ID')
        logger.critical(
            f"Отсутствуют переменные окружения: {', '.join(missing_tokens)}"
        )
        raise ValueError(
            f"Отсутствуют переменные окружения: {', '.join(missing_tokens)}"
        )


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Отправка запроса к эндпоинту."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as request_error:
        logger.error(f'Произошла ошибка запроса: {request_error}')
        raise requests.RequestException(
            f'Произошла ошибка запроса: {response.status_code}'
        )
    if response.status_code != requests.codes.ok:
        logger.error(f'API вернул код состояния: {response.status_code}')
        raise requests.HTTPError(
            f'API вернул код состояния: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка ответа от API."""
    try:
        homeworks = response['homeworks']
    except KeyError:
        raise KeyError('В ответе API отсутствует ключ "homeworks"')
    if not isinstance(homeworks, list):
        logger.error('Ожидается список с данными о домашней работе')
        raise TypeError('Данные под ключом "homeworks" не являются списком')
    if not homeworks:
        next_timestamp = response['current_date']
        logger.debug('Нет новых статусов')
        return next_timestamp
    else:
        return homeworks[0]


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('В данных отсутствует ключ "homework_name"')
    if homework['status'] == 'approved':
        verdict = HOMEWORK_VERDICTS['approved']
    elif homework['status'] == 'reviewing':
        verdict = HOMEWORK_VERDICTS['reviewing']
    elif homework['status'] == 'rejected':
        verdict = HOMEWORK_VERDICTS['rejected']
    else:
        logger.error(f'Неожиданный статус домашней работы: "{homework_name}"')
        raise ValueError(
            f'Неожиданный статус домашней работы: "{homework_name}"'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            result = check_response(response)
            if isinstance(result, int):
                timestamp = result
            else:
                message = parse_status(result)
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
