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

HOMEWORK_NAME_KEY_ERROR = 'В данных отсутствует ключ "homework_name"'
UNEXPECTED_STATUS = 'Неожиданный статус домашней работы: "{}"'
STATUS_CHANGED = 'Изменился статус проверки работы "{}". {}'

def setup_logger():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(funcName)s, %(lineno)d',
        handlers= [
            logging.StreamHandler(sys.stdout),  
            logging.FileHandler(f'{__file__}.log')  
        ]
    )

logger = logging.getLogger(__name__)


# def check_tokens():
#     """Проверка наличия обязательных переменных окружения."""
#     missing_tokens = []
#     for name in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
#         # if globals()[name] is None:  
#         #     message = f'Отсутствует обязательная переменная окружения: {name}'
#         #     logger.critical(message)  
#         #     raise KeyError(message)
#         try:
#             if not globals()[name]:
#                 missing_tokens.append(name)
#         except KeyError:
#             missing_tokens.append(name)  # Добавляем ключ в список пропущенных токенов, если его нет в словаре

#     if missing_tokens:
#         message = f"Отсутствуют переменные окружения: {missing_tokens}"
#         logger.critical(message)
#         raise KeyError(message)


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
        logger.error(f'Сбой при отправке сообщения: {error}', exc_info=True)


def get_api_answer(timestamp):
    """Отправка запроса к эндпоинту."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as request_error:
        raise requests.RequestException(
            f'Произошла ошибка запроса: {response.status_code}'
        )
    if response.status_code != requests.codes.ok:
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
        raise TypeError(f'Под ключом "homeworks" объект типа {type(homeworks)}')
    if not homeworks:
        next_timestamp = response['current_date']
        logger.debug('Нет новых статусов')
        return next_timestamp
    else:
        return homeworks[0]


def parse_status(homework):
    """Парсинг статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_KEY_ERROR)
    name = homework['homework_name']
    if homework['status'] == 'approved':
        verdict = HOMEWORK_VERDICTS['approved']
    elif homework['status'] == 'reviewing':
        verdict = HOMEWORK_VERDICTS['reviewing']
    elif homework['status'] == 'rejected':
        verdict = HOMEWORK_VERDICTS['rejected']
    else:
        raise ValueError(UNEXPECTED_STATUS.format(name))
    return STATUS_CHANGED.format(name=name, verdict=verdict)


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
            checked_response = check_response(response)
            if isinstance(checked_response, int):
                timestamp = checked_response
            send_message(bot, parse_status(checked_response))
            last_error_message = None
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if str(error) != last_error_message:
                send_message(bot, message)
                last_error_message = str(error)
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
