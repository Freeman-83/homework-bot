import logging
import os
import requests
import sys
import time
from dotenv import load_dotenv
from http import HTTPStatus
from telegram import Bot
from telegram.ext import Updater
from telegram.error import TelegramError
from exceptions import HTTPStatusError, EmptyValueError, UnexpectedValueError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка доступности переменных окружения"""
    variables = {
        PRACTICUM_TOKEN: 'PRACTICUM_TOKEN',
        TELEGRAM_TOKEN: 'TELEGRAM_TOKEN',
        TELEGRAM_CHAT_ID: 'TELEGRAM_CHAT_ID'
    }
    for var, name in variables.items():
        if not var:
            message = f'Отсутствует обязательная переменная окружения {name}'
            logger.critical(message)
            sys.exit()


def send_message(bot, message):
    """Отправка сообщения в чат"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except TelegramError as error:
        logger.error(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp) -> dict:
    """Отправка запроса к эндпоинту"""
    homeworks = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    logger.debug('Запрос отправлен')
    if homeworks.status_code != HTTPStatus.OK:
        message = (f'Эндпоинт {ENDPOINT} недоступен. '
                   f'Код ответа API: {homeworks.status_code}')
        logger.error(message)
        raise HTTPStatusError(message)

    return homeworks.json()


def check_response(response):
    """Проверка ответа API"""
    if not response:
        message = 'Возврат пустого словаря'
        logger.error(message)
        raise EmptyValueError(message)

    checking_values = {type(response): dict,
                       type(response.get('homeworks')): list}
    for key, value in checking_values.items():
        if key != value:
            message = f'Некорректный тип данных: {key}'
            logger.error(message)
            raise UnexpectedValueError(message)

    checking_values = ['homeworks', 'current_date']
    for key in response:
        if key not in checking_values:
            message = f'Ключ {key} в словаре отсутствует'
            logger.error(message)
            raise KeyError(message)

    try:
        homework = response.get('homeworks')[0]
        return homework
    except IndexError:
        message = 'Статус проверки работы не изменился'
        logger.debug(message)


def parse_status(homework):
    """Получение информации об обновлении статуса проверки"""
    try:
        homework_name = homework.get('homework_name')
        status = homework.get('status')
        verdict = HOMEWORK_VERDICTS[status]
        message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
        logger.debug(message)
    except KeyError as error:
        message = f'Статус проверки не соответствует ожидаемым вариантам: {error}'
        logger.error(message)

    return message


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = Bot(token=TELEGRAM_TOKEN)
    updater = Updater(token=TELEGRAM_TOKEN)
    timestamp = {'from_date': 1679119678}  # current_date

    while True:
        try:
            updater.start_polling()
            response = get_api_answer(timestamp)

            current_date = response.get('current_date')
            timestamp = {'from_date': current_date}

            check_result = check_response(response)
            if check_result:
                message = parse_status(check_result)
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
