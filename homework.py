import logging
import os
import requests
import sys
import time

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

HOMEWORK_NAME_KEY_ERROR = 'В данных отсутствует ключ "homework_name"'
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы: "{}"'
STATUS_CHANGED = 'Изменился статус проверки работы "{}". {}'
MISSING_TOKENS = 'Отсутствуют переменные окружения: {}'
REQUEST_ERROR = (
    'Произошла ошибка запроса: {}.'
    'Параметры запроса: ENDPOINT={}, HEADERS={}, params={{"from_date": {}}}'
)
API_RESPONSE_ERROR = (
    'Ошибка ответа: {}.'
    'Параметры запроса: ENDPOINT={}, HEADERS={}, params={{"from_date": {}}}'
)
API_DATA_ERROR = 'Ошибка ответа API: {}'
NOT_DICT_ERROR = 'Данные ответа API не являются словарем, тип объекта {}'
NO_HOMEWORKS_KEY = 'В ответе API отсутствует ключ "homeworks"'
NOT_LIST_ERROR = (
    'Данные под ключом "homeworks" не являются списком, тип объекта {}'
)
SEND_MESSAGE_SUCCESS = 'Сообщение успешно отправлено: {}'
SEND_MESSAGE_ERROR = 'Сбой при отправке сообщения: {}, exc_info=True'
NO_CHANGES = 'Нет изменений в статусе домашней работы'
PROGRAM_FAILURE = 'Сбой в работе программы: {}'


def setup_logger():
    """Настройка логгера."""
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s, %(levelname)s, %(message)s,'
            '%(name)s, %(funcName)s, %(lineno)d'
        ),
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{__file__}.log')
        ]
    )


logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка наличия обязательных переменных окружения."""
    missing_tokens = []
    for name in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
        if name not in globals() or not globals()[name]:
            missing_tokens.append(name)
    if missing_tokens:
        message = MISSING_TOKENS.format(missing_tokens)
        logger.critical(message)
        raise KeyError(message)


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message))
    except Exception as error:
        logger.error(SEND_MESSAGE_ERROR.format(error))


def get_api_answer(timestamp):
    """Отправка запроса к эндпоинту."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as request_error:
        raise Exception(
            REQUEST_ERROR.format(request_error, ENDPOINT, HEADERS, timestamp)
        )
    if response.status_code != requests.codes.ok:
        raise Exception(
            API_RESPONSE_ERROR.format(
                response.status_code, ENDPOINT, HEADERS, timestamp
            )
        )
    data = response.json()
    if 'code' in data or 'error' in data:
        message = API_DATA_ERROR.format(
            data['code'] if 'code' in data else data['error']
        )
        raise Exception(message)
    return data


def check_response(response):
    """Проверка ответа от API."""
    if not isinstance(response, dict):
        raise TypeError(NOT_DICT_ERROR.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(NO_HOMEWORKS_KEY)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(NOT_LIST_ERROR.format(type(homeworks)))
    return homeworks


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    print(homework)
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_KEY_ERROR)
    name = homework['homework_name']
    match homework['status']:
        case 'approved':
            verdict = HOMEWORK_VERDICTS['approved']
        case 'reviewing':
            verdict = HOMEWORK_VERDICTS['reviewing']
        case 'rejected':
            verdict = HOMEWORK_VERDICTS['rejected']
        case _:
            raise ValueError(UNEXPECTED_STATUS.format(name))
    return STATUS_CHANGED.format(name, verdict)


def main():
    """Основная логика работы бота."""
    setup_logger()
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                send_message(bot, parse_status(homework))
                last_error_message = None
            logger.debug(NO_CHANGES)
        except Exception as error:
            message = PROGRAM_FAILURE.format(error)
            if str(error) != last_error_message:
                send_message(bot, message)
                last_error_message = str(error)
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
