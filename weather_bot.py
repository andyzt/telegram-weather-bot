import telepot
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton
from telepot.delegate import per_chat_id, create_open, pave_event_space
import sys
import time
import pyowm
import urllib
from py_ms_cognitive_search.py_ms_cognitive_image_search import PyMsCognitiveImageSearch
import csv
import json
from bs4 import BeautifulSoup, Tag
from requests import get
from random import randint
import datetime
from dateutil import tz

# country decoding dictionaries
class Country:
    names_eng = {}
    names_full_eng = {}
    iso2 = {}
    names_rus = []

class Periods:
    daytime = {'утром': 8, 'днем': 13, 'днём': 13, 'вечером': 18, 'ночью': 23}
    dayweek = {'понедельник': 1, 'вторник': 2, 'среду': 3, 'четверг': 4,
               'пятницу': 5, 'субботу': 6, 'воскресенье': 7}
    closedays = {'завтра': 1, 'послезавтра': 2}

weather_rus = {}

owm = pyowm.OWM(language='ru',API_key='84c4e6b84effb569c25d645bc5e02796', version='2.5')

TELEGRAM_TOKEN = '301781569:AAGbcG5X3CScuewPbWzoIZ8bgkzXsJyFBzw'

def fill_dictionaries():
    with open('countries.csv', 'r') as csvfile:
        countryreader = csv.reader(csvfile, delimiter=';')
        for row in countryreader:
            Country.names_eng[row[4]] = row[0]
            Country.names_full_eng[row[3]] = row[0]
            Country.iso2[row[6]] = row[0]
            Country.names_rus.append(row[2])

    global weather_rus
    with open('weather_rus.json') as json_data:
        weather_rus = json.load(json_data)


def get_poetry(query):
    req = get('http://poetory.ru/content/list?query=' + query)
    try:
        soup = BeautifulSoup(req.text, "html5lib")
        poetry = soup.findAll('div', attrs={'class': 'item-text'})
        if (len(poetry) > 0):
            sample = poetry[randint(0, len(poetry) - 1)]

            soup2 = BeautifulSoup(str(sample), "html5lib")
            for tag in soup2.findAll(True):
                if tag.name != "br":
                    tag.append('')
                    tag.replaceWithChildren()
            result = str(soup2).replace("<br/>", "\n")
            return result
        else:
            raise ValueError('poetry not found')
    except:
        raise ValueError('poetry not found')


def get_season():
    month = datetime.date.today().month
    if 9 <= month < 12:
        return 'осень'
    elif 6 <= month:
        return 'лето'
    elif 3 <= month:
        return 'весна'
    else:
        return 'зима'


def get_picture(city, weather):
    search_term = city + ' ' + get_season() + ' ' + weather
    search_service = PyMsCognitiveImageSearch('6fb4c9eebd904da7996a4a66848805da', search_term)
    five_results = search_service.search(limit=5, format='json')
    if len(five_results) > 0:
        for i in range(5):
            try:
                num = randint(0, len(five_results) - 1)
                req = urllib.request.Request(five_results[num].__dict__['content_url'],
                                             headers={'User-Agent': 'Mozilla/5.0'})
                img = urllib.request.urlopen(req)
                return img
            except:
                continue
    raise ValueError('picture not found')


def compose_msg(city, weather):
    status = weather.get_status()
    description = weather.get_detailed_status()

    if (description[0] >= 'A' and description[0] <= 'z'):  #Russian locale is not working
        description = weather_rus[status]

    temperature = weather.get_temperature('celsius')
    if 'temp_max' in temperature.keys():
        temp_value = (temperature['temp_max'] + temperature['temp_min']) // 2
    else:
        temp_value = temperature['day']

    msg = "Прогноз погоды в городе " + city + " на "
    msg += time.strftime("%d/%m/%Y %H:%M", time.localtime(weather.get_reference_time())) + '\n'
    msg += description + ", температура: " + str(temp_value) + '°C\n'
    msg += 'Ветер: ' + str(weather.get_wind()['speed']) + " м/с"

    return msg, weather_rus[status]


def get_next_days_time(days_num):
    now_date = datetime.date.today()
    delta = datetime.timedelta(days=days_num)
    new_date = now_date + delta
    t = datetime.time(9, 0, 0)
    return datetime.datetime.combine(new_date, t)


def parse_period(period):
    if (period[0] == 'now'):
        return 'now', None
    elif period[0] == 'в' or period[0] == 'во':
        if period[1] in Periods.dayweek.keys():
            num_day = datetime.date.today().isoweekday()
            diff = num_day - Periods.dayweek[period[1]]
            if diff < 0:
                diff += 7
            if diff > 5:
                return 'far', None
            else:
                return 'far', get_next_days_time(diff)
        else:
            return None
    elif period[0] == 'через':
        if int(period[1]) < 1 or int(period[1]) > 5:
            return 'far', None
        else:
            return 'far', get_next_days_time(int(period[1]))
    else:
        if period[0] in Periods.daytime.keys():
            HERE = tz.tzlocal()
            t = datetime.time(Periods.daytime[period[0]] - 3, 0, 0)
            result = datetime.datetime.combine(datetime.date.today(), t)
            result = result.replace(tzinfo=HERE)
            if result < datetime.datetime.now(HERE):
                return 'close', result + datetime.timedelta(days=1)
            else:
                return 'close', result

        elif period[0] in Periods.closedays.keys():
            return 'far', get_next_days_time(Periods.closedays[period[0]])
        else:
            return 'far', None


def add_country(location):
    country_id = int(Country.names_eng.get(location.get_country(), "-1"))
    if country_id == -1:
        country_id = int(Country.iso2.get(location.get_country(), "-1"))
    if country_id == -1:
        country_id = int(Country.names_full_eng.get(location.get_country(), "-1"))
    if country_id == -1:
        return str(location.get_ID()), location.get_name(), location.get_country()
    else:
        return str(location.get_ID()), location.get_name(), Country.names_rus[country_id]


class MessageHandler(telepot.helper.ChatHandler):
    def __init__(self, *args, **kwargs):
        super(MessageHandler, self).__init__(*args, **kwargs)
        self.request = ""
        self.city_dict = {}

    def process_query(self, city_ID, city_name, country, period):
        try:
            type, dt = parse_period(period)
            if type == 'now':
                obs = owm.weather_at_id(int(city_ID))
                weather = obs.get_weather()
            elif type == 'close':
                forecast = owm.three_hours_forecast_at_id(int(city_ID))
                weather = forecast.get_weather_at(dt)
            else:
                forecast = owm.daily_forecast_at_id(int(city_ID))
                weather = forecast.get_weather_at(dt)
        except pyowm.exceptions.OWMError as e:
            self.sender.sendMessage("Ошибка определения погоды")
            return

        msg, status = compose_msg(city_name + ', ' + country, weather)
        self.sender.sendMessage(msg, reply_markup={'remove_keyboard': True})
        try:
            self.sender.sendPhoto(('image.jpg', get_picture(city_name, status)))
        except ValueError as e:
            self.sender.sendMessage("Я не смог найти картинку по этому запросу")

        try:
            self.sender.sendMessage(get_poetry(status))
        except ValueError as e:
            self.sender.sendMessage("Я не смог найти стишок по этому запросу")

        return

    def on_chat_message(self, msg):

        content_type, chat_type, chat_id = telepot.glance(msg)

        if content_type == 'text':
            command = msg['text'].strip().lower()
            if command == '/start' or command == '/help':
                msg = "Привет! Я могу подсказать погоду в любом городе.\n"
                msg += "Все, что нужно - это отправить название города и (необязательно) период\n"
                msg += "Например: 'Москва' или 'Москва в четверг' или 'Москва вечером' \n"
                msg += "Так же можно писать 'Москва через 5 дней' - но не более 5 дней\n"
                msg += "Если повезет, то вас ждут картинка и стишок на тему погоды"
                self.sender.sendMessage( msg)
            elif command[0] == '/':
                if msg['text'] not in self.city_dict.keys():
                    self.sender.sendMessage("Неизвестная команда")
                    return

                city_info = msg['text'][1:].split(', ')
                self.process_query(self.city_dict[msg['text']],
                                   city_info[0], city_info[1], self.period)
                self.city_dict = {}
            else:
                parsed_request = msg['text'].split(' ')
                city = parsed_request[0]
                if len(parsed_request) > 1:
                    self.period = parsed_request[1:]
                    type, value = parse_period(self.period)
                    if value == None:
                        self.sender.sendMessage("Не могу определелить погоду за указанный период")
                        return
                else:
                    self.period = ['now']

                try:
                    obs_list = owm.weather_at_places(city, 'like')
                except pyowm.exceptions.OWMError as e:
                    self.sender.sendMessage("Название города некорректно")
                    return

                if obs_list is None or len(obs_list) == 0:
                    self.sender.sendMessage("Города с таким именем не найдено")
                    return

                if len(obs_list) == 1:
                    city_id, city_name, country = add_country(obs_list[0].get_location())
                    self.process_query(city_id, city_name, country, self.period)
                    return

                city_list = []
                for obs in obs_list:
                    city_list.append(add_country(obs.get_location()))

                if len(obs_list) > 1:
                    buttons = []
                    for city in city_list:
                        text = '/'+city[1] + ', ' + city[2]
                        if text in self.city_dict.keys():
                            text += ', ' + city[0]
                        self.city_dict[text] = city[0]
                        buttons.append(KeyboardButton(
                            text=text))
                    keyboard = ReplyKeyboardMarkup(keyboard=[buttons])

                    self.sender.sendMessage('Выберите город из списка', reply_markup=keyboard)
                    return

        else:
            self.sender.sendMessage("Я не понимаю такой запрос")


if __name__ == "__main__":
    fill_dictionaries()

    bot = telepot.DelegatorBot(TELEGRAM_TOKEN, [
        pave_event_space()(
            per_chat_id(), create_open, MessageHandler, timeout=20
        ),
    ])
    bot.message_loop(run_forever='Listening ...')