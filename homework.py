import logging
import os
import sys
import time

from dotenv import load_dotenv
from telebot import TeleBot
import requests

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
REQUEST_PARAMETERS = (
    'Параметры запроса: url={url}, headers={headers}, params={params}'
)
REQUEST_ERROR = ('Произошла ошибка запроса: {}. ' + REQUEST_PARAMETERS)
API_RESPONSE_ERROR = ('Ошибка ответа: {}.' + REQUEST_PARAMETERS)
API_DATA_ERROR = ('Ключ ответ API: "{}", Значение: {}. ' + REQUEST_PARAMETERS)
NOT_DICT_ERROR = 'Данные ответа API не являются словарем, тип объекта {}'
NO_HOMEWORKS_KEY = 'В ответе API отсутствует ключ "homeworks"'
NOT_LIST_ERROR = (
    'Данные под ключом "homeworks" не являются списком, тип объекта {}'
)
SEND_MESSAGE_SUCCESS = 'Сообщение успешно отправлено: {}'
SEND_MESSAGE_ERROR = 'Сбой при отправке сообщения: {}, exc_info=True'
STATUS_NO_CHANGED = 'Статус домашней работы не изменился'
PROGRAM_FAILURE = 'Сбой в работе программы: {}'

tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка наличия обязательных переменных окружения."""
    missing_tokens = [
        name for name in tokens if
        name not in globals() or not globals()[name]
    ]
    if missing_tokens:
        message = MISSING_TOKENS.format(missing_tokens)
        logger.critical(message)
        raise ValueError(message)


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message))
        return True
    except Exception as error:
        logger.error(SEND_MESSAGE_ERROR.format(error))
        return False


def get_api_answer(timestamp):
    """Отправка запроса к эндпоинту."""
    params = {'from_date': timestamp}
    request_parameters = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**request_parameters)
    except requests.RequestException as request_error:
        raise ConnectionError(
            REQUEST_ERROR.format(request_error, **request_parameters)
        )
    if response.status_code != requests.codes.ok:
        raise ValueError(
            API_RESPONSE_ERROR.format(
                response.status_code,
                **request_parameters
            )
        )
    data = response.json()
    for error_key in ['code', 'error']:
        if error_key in data:
            raise ValueError(
                API_DATA_ERROR.format(
                    error_key,
                    data[error_key],
                    **request_parameters
                )
            )
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
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_KEY_ERROR)
    status = homework['status']
    name = homework['homework_name']
    if status in HOMEWORK_VERDICTS:
        return STATUS_CHANGED.format(name, HOMEWORK_VERDICTS[status])
    raise ValueError(UNEXPECTED_STATUS.format(status))


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                if send_message(bot, parse_status(homeworks[0])):
                    timestamp = response.get('current_date', timestamp)
                    last_error_message = None
            logger.debug(STATUS_NO_CHANGED)
        except Exception as error:
            message = PROGRAM_FAILURE.format(error)
            logger.error(message)
            if message != last_error_message:
                if send_message(bot, message):
                    last_error_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
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
    main()
