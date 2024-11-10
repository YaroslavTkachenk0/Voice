import telebot
import speech_recognition
from pydub import AudioSegment
from pydub.utils import make_chunks
import os 
import sqlite3

token = 'Токен от ТГ бота'
languages = {'/language_en': 'en', '/language_de': 'de', '/language_ru': 'ru', '/language_uk': 'uk'}
bot = telebot.TeleBot(token)

# Start
@bot.message_handler(commands=['start'])
def start(message) -> None:
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}")
    conn = sqlite3.connect('Voice.db')
    cur = conn.cursor()

    cur.execute('CREATE TABLE IF NOT EXISTS users (id_user INTEGER primary key,  name varchar(50), language varchar(50), interface_language varchar(50))')

    cur.execute("INSERT INTO users (id_user, name, language, interface_language) VALUES ('%s', '%s', '%s', '%s') \
                ON CONFLICT (id_user) DO UPDATE SET name = '%s', language = '%s', interface_language = '%s'" 
                % (message.from_user.id, message.from_user.first_name, message.from_user.language_code, 
                    message.from_user.language_code, message.from_user.first_name, message.from_user.language_code, message.from_user.language_code))
    conn.commit()
    cur.close()
    conn.close()

# Получение информации о пользователе
@bot.message_handler(commands=['user_info'])
def user_information(message) -> None:
    bot.send_message(message.chat.id, message)

# Список доступных языков	
@bot.message_handler(commands=['languages'])
def language_settings(message) -> None:
    text = 'Список доступных языков: \n\
        <b>Английский</b> - /language_en\n\
        <b>Немецкий</b> - /language_de\n\
        <b>Русский</b> - /language_ru\n\
        <b>Украинский</b> - /language_uk '
    bot.send_message(message.chat.id, text, parse_mode='html')

# Проверка языка
def languge_check(message) -> tuple[str, bool]:
    conn = sqlite3.connect('Voice.db')
    cur = conn.cursor()
    check_res = True
    try:
        cur.execute("SELECT language FROM users  WHERE id_user='%s'" % message.from_user.id)
        language = cur.fetchall()[0][0]
    except IndexError:
        check_res = False
        language = 'ru'
        bot.send_message(message.chat.id, 'Для распознавания других языков введите /start')
    finally:
        cur.close()
        conn.close()
    return language , check_res

# Смена языка распознавания 
@bot.message_handler(commands=['language_en', 'language_de', 'language_ru', 'language_uk'])
def switch_language(message) -> None:
    conn = sqlite3.connect('Voice.db')
    cur = conn.cursor()
    cur.execute("UPDATE users SET language = ?  WHERE id_user = ?", (languages[message.text], message.from_user.id))
    conn.commit()
    cur.close()
    conn.close()
    language, check_res = languge_check(message)
    if check_res:
        bot.send_message(message.chat.id, language)

# Скачивание файла, который прислал пользователь
def download_file(bot, file_id: str) -> str:
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    filename = file_id + file_info.file_path
    filename = filename.replace('/', '_')

    with open(filename, 'wb') as file:
        file.write(downloaded_file)

    return filename

# Конвертация формата файлов
def oga_or_mp4_to_flac(filename: str) -> tuple[str, bool]:
    # Переименование формата: 'sample.oga' или 'sample.mp4' -> 'sample.flac'
    new_filename = os.path.splitext(filename)[0] + '.flac'
    # Читаем файл с диска с помощью функции AudioSegment.from_file()
    audio = AudioSegment.from_file(filename)
    long_audio = False  # аудио длиннее 2 минут
    duration = 120_000  # 2 мин в мс
    if len(audio) > duration:  
        # Разбиваем аудио на чанки продолжительностью 120 секунд
        chunks = make_chunks(audio, duration)
        # Экспортируем первые 2 мин аудио в новый файл 
        chunks[0].export(new_filename, format='flac')
        long_audio = True
    else:
        # Экспортируем файл в новом формате
        audio.export(new_filename, format='flac')
    # Возвращаем в качестве результата функции имя нового файла и флаг
    return new_filename, long_audio

# Перевод голоса в текст + удаление использованных файлов
def recognize_speech(audiovideo_filename: str, message) -> str:
    language, _ = languge_check(message)

    flac_filename, long_audio = oga_or_mp4_to_flac(audiovideo_filename)
    recognizer = speech_recognition.Recognizer()

    if long_audio:
        bot.send_message(message.chat.id, 'Аудио сообщение слишком длинное. \nБудет распознано первые 2 минуты аудио сообщения')

    with speech_recognition.WavFile(flac_filename) as source:
        flac_audio = recognizer.record(source)
        recognizer.adjust_for_ambient_noise(source, 0.5)

    if os.path.exists(audiovideo_filename):
        os.remove(audiovideo_filename)
        
    if os.path.exists(flac_filename):
        os.remove(flac_filename)
        
    try:
        text = recognizer.recognize_google(flac_audio, language=language)

    except (speech_recognition.exceptions.UnknownValueError, speech_recognition.exceptions.RequestError):
        text = '...'
    
    return text

# Отправка текста в ответ на голосовое и видео сообщение
@bot.message_handler(content_types=['voice', 'video_note'])	
def transcript(message) -> None:
    if message.content_type == 'voice':
        filename = download_file(bot, message.voice.file_id)
    else:
        filename = download_file(bot, message.video_note.file_id)
    
    text = recognize_speech(filename, message)
    bot.send_message(message.chat.id, text)

# Help
@bot.message_handler(commands=['help'])
def info_help(message) -> None:
    text = "Список доступных команд:\n"\
        "<b>Перезапуск бота</b> - /start\n"\
        "<b>Список доступных языков</b> - /languages"    
    bot.send_message(message.chat.id, text, parse_mode='html')

bot.infinity_polling()











