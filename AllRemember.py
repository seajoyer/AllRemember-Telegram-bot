import telebot
from telebot import types
import datetime
import time
import mysql.connector
import json
import re
import difflib
import sys


def get_curr_time(t_z=0):
    # t_z - time zone
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=t_z)
    return(int(now.timestamp()))


def get_next_date(delta, t_z=0):
    # delta - number of hours, which need add
    date = datetime.datetime.utcnow() + datetime.timedelta(minutes=delta) + datetime.timedelta(hours=t_z) 
    date.replace(hour=0, minute=0, second=0, microsecond=0)
    return(int(date.timestamp()))
    
    
def db_select(query):
    try:      
        cursor.execute(query)
        res = cursor.fetchall()
    except:
        res = []
    return(res)


def db_edit(mode, query, val=None):
    try:
        if mode == 'execute':
            cursor.execute(query, val)
            db.commit() 
        elif mode == 'executemany':
            cursor.executemany(query, val)
            db.commit() 
    except:
        pass

        
def sm2(x: [int], a=0.9, b=-1.2, c=0.2, d=0.03, theta=0.3) -> int:
    """
    Returns the number of days to delay the next review of an item by, fractionally, based on the history of answers x to
    a given question, where
    x == 0: Incorrect, Hardest
    x == 1: Incorrect, Hard
    x == 2: Incorrect, Medium
    x == 3: Correct, Medium
    x == 4: Correct, Easy
    x == 5: Correct, Easiest
    @param x The history of answers in the above scoring.
    @param theta When larger, the delays for correct answers will increase.
    """
    assert all(0 <= x_i <= 5 for x_i in x)
    correct_x = [x_i >= 3 for x_i in x]   
    # Calculate the latest consecutive answer streak
    num_consecutively_correct = 0
    for correct in reversed(correct_x):
        if correct:
            num_consecutively_correct += 1
        else:
            break  
    return int(1440*a*(max(1.3, 2.5 + sum(b+c*x_i+d*x_i*x_i for x_i in x)))**(theta*num_consecutively_correct))


def calculate_buttons(x):
    correct_quality = [x_i >= 3 for x_i in x]
    if len(x) == 0 or True not in correct_quality:
        buttons_time = [1, None, None, 10, 5760]
    elif correct_quality.count(True) == 1 and x[-1] == 4:
        buttons_time = [1, None, None, 1440, 5760]
    elif True in correct_quality and correct_quality[-1] == False:
        buttons_time = [None, 10, None, 1440, None]
    else:
        buttons_time = [None, 10, sm2(x+[3]), sm2(x+[4]), sm2(x+[5])]

    buttons_caption = []
    start_days = 1
    for idx in range(len(buttons_time)):
        if buttons_time[idx] == None:
            buttons_caption.append(None)
        elif buttons_time[idx] == 1:
            buttons_caption.append('<1 мин')
        elif buttons_time[idx] == 10:
            buttons_caption.append('<10 мин')
        else:
            days = int(buttons_time[idx]/1440)
            if days < start_days:
                days = start_days
            start_days = days
            start_days += 1
            buttons_time[idx] = days * 1440
            buttons_caption.append("%d дн" % (days))
    return([buttons_time, buttons_caption])


def ndiff(s1, s2):
    # s1 user's input
    # s2 true word
    tmp1 = []
    tmp2 = []
    prev = ''
    teg = ('<b><ins>', '</ins></b>')
    s1 = s1.lower()
    s2 = s2.lower()
    #teg = ('<s>', '</s>')
    for i,s in enumerate(difflib.ndiff(s1, s2)):
        if s[0] == ' ':
            tmp1.append(s[2])
            tmp2.append(s[2])
        elif s[0] == '-':
            tmp1.extend((teg[0], s[2], teg[1]))
        elif s[0] == '+':
            if prev != '-':
                tmp1.append('-')
            tmp2.extend((teg[0], s[2], teg[1]))
        prev = s[0]
    return((''.join(tmp1), ''.join(tmp2)))



path = '/home/osboxes/work/AnkiBot/media/'
host='localhost'
database='Anki'
user='phpmyadmin'
password='123'
admin_id = 653376416

token = '1009351025:AAHdYuZOS8Xiom8_JujWI50VGE2LHXHQeEE'
bot = telebot.TeleBot(token)

db = mysql.connector.connect(host=host, database=database, user=user, password=password)   
cursor = db.cursor()

default_options = {'new_cards': 10,
                   'time_zone': 2}
users_info = {}
result = db_select("""SELECT user_id, first_name, last_visit, SSE_4000_EEW, time_zone FROM users """)
for item in result:
    if len(item) == 5:
        users_info[item[0]] = {'first_name': item[1], 'last_visit': item[2], 'SSE_4000_EEW': json.loads(item[3]),
                               'time_zone': item[4], 'user_reply': False, 'curr_table': '', 'word_id': None}
        

@bot.message_handler(commands=["start"])
def handle_message(message):
    curr_time = get_curr_time()
    if message.from_user.id not in users_info:     
        key = types.ReplyKeyboardMarkup(one_time_keyboard = True, row_width=1, resize_keyboard=True)
        key.row('колоды', 'помощь')
        key.row('сотрудничество')
        bot.send_message(message.chat.id, "Привет, " + str(message.from_user.first_name) + ", этот бот работает по алгоритму SuperMemo2, он поможет тебе запомнить различную информацию. Например новые слова иностроннаго языка, формулы точных наук, исторические даты и многое другое! \n\n Вопросы и предложения - @Garison_777.",reply_markup=key)

        #Add new user
        word_set = {'new': [], 'learning': [], 'to_review': [], 
                    'last_visit': 0, 'n_cards': default_options['new_cards'], 'learned_today': 0}
        db_edit('execute', """INSERT INTO users (id, user_id, first_name, last_name, username, first_visit, last_visit, SSE_4000_EEW, time_zone) VALUES (NULL, '%d', '%s', '%s', '%s', '%d', '%d', '%s', '%d')""" % (message.from_user.id, message.from_user.first_name, message.from_user.last_name, message.from_user.username, curr_time, curr_time, json.dumps(word_set), default_options['time_zone']))
        users_info[message.from_user.id] = {'first_name': message.from_user.first_name, 'last_visit': curr_time,
                                            'SSE_4000_EEW': word_set, 'time_zone': default_options['time_zone'],
                                            'user_reply': False, 'curr_table': '', 'word_id': None}
                              
        #Add new user to time tabble
        result = db_select("""SELECT id FROM SSE_4000_EEW """)
        values = [(message.from_user.id, item[0], 0) for item in result]
        db_edit('executemany', """INSERT INTO date_SSE_4000_EEW (user_id, word_id, date) VALUES ('%s', '%s', '%s') """, values)
    else:
        key = types.ReplyKeyboardMarkup(one_time_keyboard = True, resize_keyboard=True)
        key.row('колоды', 'помощь')
        key.row('сотрудничество')
        bot.send_message(message.chat.id, "Используй меню ниже для управления ботом", reply_markup=key)
        db_edit('execute', """UPDATE users SET last_visit = '%d' WHERE user_id = '%d'""" % (curr_time, message.from_user.id))
        
        
#    print(message.from_user.id)

    
@bot.message_handler(func=lambda c:True, content_types=['text'])
def info_message(message):
    if message.chat.id in users_info and message.text not in ['колоды', 'помощь', 'сотрудничество']:  
        if users_info[message.chat.id]['user_reply']:
            users_info[message.chat.id]['user_reply'] = False
            quality = []
            word_id = users_info[message.chat.id]['word_id']
            curr_table = users_info[message.chat.id]['curr_table']
            # Select quality hystory
            if word_id != None:
                result = db_select("""SELECT quality FROM date_%s WHERE user_id = '%d' and word_id = '%d' and quality IS NOT NULL """ % (curr_table, message.chat.id, word_id)) 
                if len(result) != 0:
                    for (item,) in result:
                        quality = json.loads(item)
                        break 

            buttons_time, buttons_caption = calculate_buttons(quality)
            scores = [0,2,3,4,5]
            but_list = []
            key = types.InlineKeyboardMarkup()
            for idx in range(len(buttons_time)):
                if buttons_time[idx] != None:
                    c_d = ''.join(['Interval', ';', str(buttons_time[idx]), ';', str(word_id), ';', str(scores[idx]), '|', curr_table])
                    but_list.append(types.InlineKeyboardButton(text=buttons_caption[idx], callback_data=c_d))
            key.add(*but_list) 

            result = db_select("""SELECT * FROM %s WHERE id = '%d' """ % (curr_table, word_id))
            for res in result:
                if len(res) == 11:
                    english = re.sub('{{\w*::\w*}}', res[4], res[3])
                    bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id-1, text=english, reply_markup = '')
                    keybt = types.ReplyKeyboardMarkup(one_time_keyboard = True, row_width=1, resize_keyboard=True)
                    user_input, keyword = ndiff(message.text, res[4])
                    caption = user_input + '\n' + keyword + '\n' + res[5] + '\n' + res[6]
                    bot.send_voice(message.chat.id, caption =caption, parse_mode= 'HTML', voice=open(path+res[7], 'rb'), reply_markup=key)
                    break
            
        if 'cooperation' in users_info[message.chat.id]:
            if users_info[message.chat.id]['cooperation']:
                bot.send_message(admin_id, "Message from %d %s\n%s" % (message.chat.id, message.from_user.username, message.text))
                users_info[message.chat.id]['cooperation'] = False

    if message.chat.id in users_info:
        users_info[message.chat.id]['user_reply'] = False
        users_info[message.chat.id]['cooperation'] = False         
        
        if message.text == 'колоды': 
            key = types.InlineKeyboardMarkup()
            but_1 = types.InlineKeyboardButton(text="4000 Essential English Words",callback_data="EssEng|SSE_4000_EEW")
            key.add(but_1)
            msg = bot.send_message(message.chat.id, "Выбери колоду для изучения:", reply_markup=key)

        if message.text == 'сотрудничество' and message.chat.id in users_info:
            users_info[message.chat.id]['cooperation'] = True 
            key = types.InlineKeyboardMarkup()
            but_1 = types.InlineKeyboardButton(text="Отмена",callback_data="Cancel")
            key.add(but_1)
            bot.send_message(message.chat.id, "Напиши мне, в каком формате ты хочешь предложить сотрудничество со мной.\nЕсли передумал, нажми отмена.", reply_markup=key)

        if message.text == 'помощь':
            msg = """@AllRememberBOT работает по модифицированному алгоритму SuperMemo 2, он поможет тебе с легкостью выучить иностранные слова, столицы, формулы различных наук, исторические даты и многое другое!


📱 Теперь по поводу интерфейса, у каждой колоды есть несколько параметров:
    🌐Новые - количество новых элементов на сегодня
    🔵Обучение - элементы требующие повторения в процессе обучения (в рамках одного дня) 
    🔴Проверить - элементы которые будут повторены с прошлых дней обучения


📈 В процессе обучения, будет предложено выбрать через какое время повторить изучаемый элемент:
    🕐<1 мин - трудно, элемент будет показан через минуту
    🕑 <10 мин - элемент будет показан через 10 минут (для новых - хорошо, для изученных - трудно)
    📆 Если же вы отлично выучили элемент, выберите дневной интервал


⚙️ Так же для каждой колоды в разделе "настройки" можно настроить количество новых элементов в день и ваш часовой пояс, это необходимо для коректного обновления карточек в 00:00. По умолчанию он равен UTC+02:00.


💬 На данный момент доступны колоды:
    3600 Essential words - 3600 важнейших англ. слов
(Новые колоды в разработке)"""
            bot.send_message(message.chat.id, msg)
        
    
@bot.callback_query_handler(func=lambda c:True)
def inline(c):
    if c.message.chat.id not in users_info:
        bot.send_message(c.message.chat.id, "Введите /start", reply_markup='')      
    else:
        users_info[c.message.chat.id]['cooperation'] = False
        users_info[c.message.chat.id]['user_reply'] = False
        curr_time = get_curr_time()
        call_back_data = ''
        curr_table = None
        tmp = str(c.data)
        call_back_data = tmp
        # Last visit update
        users_info[c.message.chat.id]['last_visit'] = curr_time
        curr_time = get_curr_time(users_info[c.message.chat.id]['time_zone'])
        if '|' in tmp:
            call_back_data, curr_table = tmp.split('|')
            if curr_table in users_info[c.message.chat.id]:
                update = False
                word_set = users_info[c.message.chat.id][curr_table]
                last_visit = datetime.datetime.fromtimestamp(word_set['last_visit'])
                curr_date = datetime.datetime.utcnow() + datetime.timedelta(hours=users_info[c.message.chat.id]['time_zone'])
                if last_visit.year != curr_date.year or last_visit.month != curr_date.month or last_visit.day != curr_date.day:
                    update = True   

                if update:
                    result = db_select("""SELECT word_id FROM date_SSE_4000_EEW WHERE user_id = '%d' and date = 0 LIMIT %d """ % (c.message.chat.id, word_set['n_cards']))        
                    result = [i for sub in result for i in sub]
                    word_set['new'] = result
                    result = db_select("""SELECT word_id FROM date_SSE_4000_EEW WHERE user_id = '%d' and date < '%d' and date > 0""" % (c.message.chat.id, curr_time))        
                    result = [i for sub in result for i in sub]
                    word_set['to_review'] = result
                    word_set['last_visit'] = curr_time  
                    word_set['learned_today'] = 0
                    db_edit('execute', """UPDATE users SET SSE_4000_EEW = '%s' WHERE user_id = '%d'""" % (json.dumps(word_set), c.message.chat.id))
                    users_info[c.message.chat.id]['SSE_4000_EEW'] = word_set 
        # Last visit update
        users_info[c.message.chat.id]['last_visit'] = curr_time
        if call_back_data not in ['reduce cards', 'increase cards', 'save n cards', 'reduce time zone', 'increase time zone', 'save time zone']:
            db_edit('execute', """UPDATE users SET last_visit = '%d' WHERE user_id = '%d'""" % (curr_time, c.message.chat.id))
#        print('c.data = ', c.data)

        
        if "EssEng" in c.data:       
            word_set = users_info[c.message.chat.id]['SSE_4000_EEW']                
            if len(word_set['new']+word_set['learning']+word_set['to_review']) == 0:
                bot.send_message(c.message.chat.id, "Ура! На сегодня всё.")
            else:
                key = types.InlineKeyboardMarkup()
                but_1 = types.InlineKeyboardButton(text="Настройки",callback_data="Settings|SSE_4000_EEW")
                but_2 = types.InlineKeyboardButton(text="Учить",callback_data="Study|SSE_4000_EEW")
                key.add(but_1)
                key.add(but_2)    
                bot.edit_message_text(chat_id = c.message.chat.id, message_id = c.message.message_id, text = "4000 Essential English Words\nby Paul Nation:\n\n🌐Новые %d \n🔵Обучение %d \n🔴Проверить %d" % (len(word_set['new']), len(word_set['learning']), len(word_set['to_review'])), reply_markup=key)    

        if 'Settings' in call_back_data: 
            if curr_table in users_info[c.message.chat.id]:
                n_cards = users_info[c.message.chat.id][curr_table]['n_cards']
                time_zone = users_info[c.message.chat.id]['time_zone']
                key = types.InlineKeyboardMarkup()
                but_1 = types.InlineKeyboardButton(text="-",callback_data="reduce cards|"+curr_table)
                but_2 = types.InlineKeyboardButton(text="+",callback_data="increase cards|"+curr_table)
                but_3 = types.InlineKeyboardButton(text="Сохранить",callback_data="save n cards|"+curr_table)
                key.add(but_1, but_2, but_3)
                bot.send_message(c.message.chat.id, "Новых карточек в день: %d" % (n_cards), reply_markup=key) 
                key = types.InlineKeyboardMarkup()
                but_4 = types.InlineKeyboardButton(text="-",callback_data="reduce time zone")
                but_5 = types.InlineKeyboardButton(text="+",callback_data="increase time zone")
                but_6 = types.InlineKeyboardButton(text="Сохранить",callback_data="save time zone")
                key.add(but_4, but_5, but_6)
                bot.send_message(c.message.chat.id, "Часовой пояс:  UTC{:+03d}:00".format(time_zone), reply_markup=key) 

        if "reduce cards" in c.data:
            if ':' in c.message.text:
                tmp = c.message.text
                _, n_cards = tmp.split(':')
                n_cards = int(n_cards)
                if n_cards > 0:
                    n_cards -= 1
                    key = types.InlineKeyboardMarkup()
                    but_1 = types.InlineKeyboardButton(text="-",callback_data="reduce cards|"+curr_table)
                    but_2 = types.InlineKeyboardButton(text="+",callback_data="increase cards|"+curr_table)
                    but_3 = types.InlineKeyboardButton(text="Сохранить",callback_data="save n cards|"+curr_table)
                    key.add(but_1, but_2, but_3)
                    tmp = "Новых карточек в день:  %s"% (str(n_cards))
                    bot.edit_message_text(chat_id = c.message.chat.id, message_id = c.message.message_id, text = tmp, reply_markup=key)    

        if "increase cards" in c.data:
            if ':' in c.message.text:
                tmp = c.message.text
                _, n_cards = tmp.split(':')
                n_cards = int(n_cards)
                if n_cards < 100:
                    n_cards += 1
                    key = types.InlineKeyboardMarkup()
                    but_1 = types.InlineKeyboardButton(text="-",callback_data="reduce cards|"+curr_table)
                    but_2 = types.InlineKeyboardButton(text="+",callback_data="increase cards|"+curr_table)
                    but_3 = types.InlineKeyboardButton(text="Сохранить",callback_data="save n cards|"+curr_table)
                    key.add(but_1, but_2, but_3) 
                    tmp = "Новых карточек в день:  %s"% (str(n_cards))
                    bot.edit_message_text(chat_id = c.message.chat.id, message_id = c.message.message_id, text = tmp, reply_markup=key)    

        if "reduce time zone" == c.data:
            if ':' in c.message.text:
                tmp = c.message.text
                _, time_zone, _ = tmp.split(':')
                time_zone = int(time_zone.replace('UTC', ''))
                if time_zone > -12:
                    time_zone -= 1
                    key = types.InlineKeyboardMarkup()
                    but_4 = types.InlineKeyboardButton(text="-",callback_data="reduce time zone")
                    but_5 = types.InlineKeyboardButton(text="+",callback_data="increase time zone")
                    but_6 = types.InlineKeyboardButton(text="Сохранить",callback_data="save time zone")
                    key.add(but_4, but_5, but_6)
                    tmp = "Часовой пояс:  UTC{:+03d}:00".format(time_zone)
                    bot.edit_message_text(chat_id = c.message.chat.id, message_id = c.message.message_id, text = tmp, reply_markup=key)    

        if "increase time zone" == c.data:
            if ':' in c.message.text:
                tmp = c.message.text
                _, time_zone, _ = tmp.split(':')
                time_zone = int(time_zone.replace('UTC', ''))
                if time_zone < 12:
                    time_zone += 1
                    key = types.InlineKeyboardMarkup()
                    but_4 = types.InlineKeyboardButton(text="-",callback_data="reduce time zone")
                    but_5 = types.InlineKeyboardButton(text="+",callback_data="increase time zone")
                    but_6 = types.InlineKeyboardButton(text="Сохранить",callback_data="save time zone")
                    key.add(but_4, but_5, but_6)
                    tmp = "Часовой пояс:  UTC{:+03d}:00".format(time_zone)
                    bot.edit_message_text(chat_id = c.message.chat.id, message_id = c.message.message_id, text = tmp, reply_markup=key)            

        if "save n cards" in c.data:
            if curr_table in users_info[c.message.chat.id]:
                if ':' in c.message.text:
                    tmp = c.message.text
                    _, n_cards = tmp.split(':')
                    n_cards = int(n_cards)
                    if n_cards != users_info[c.message.chat.id][curr_table]['n_cards']:                        
                        users_info[c.message.chat.id][curr_table]['n_cards'] = n_cards
                        n_cards = n_cards - users_info[c.message.chat.id][curr_table]['learned_today']
                        if n_cards > 0:
                            result = db_select("""SELECT word_id FROM date_SSE_4000_EEW WHERE user_id = '%d' and date = 0 LIMIT %d """ % (c.message.chat.id, n_cards))        
                            result = [i for sub in result for i in sub]
                            users_info[c.message.chat.id][curr_table]['new'] = result  
                        else:
                            users_info[c.message.chat.id][curr_table]['new'] = []
                        db_edit('execute', """UPDATE users SET %s = '%s' WHERE user_id = '%d' """ % (curr_table, json.dumps(users_info[c.message.chat.id][curr_table]), c.message.chat.id))

        if "save time zone" == c.data:
            if ':' in c.message.text:
                tmp = c.message.text
                _, time_zone, _ = tmp.split(':')
                time_zone = int(time_zone.replace('UTC', ''))
                if users_info[c.message.chat.id]['time_zone'] != time_zone:
                    users_info[c.message.chat.id]['time_zone'] = time_zone
                    db_edit('execute', """UPDATE users SET time_zone = '%d' WHERE user_id = '%d' """ % (time_zone, c.message.chat.id))


        if 'Show_answer' in call_back_data:
            if curr_table in users_info[c.message.chat.id]:
                quality = []
                _, word_id = call_back_data.split(';')
                word_id = int(word_id)

                # Select quality hystory
                if word_id != None:
                    result = db_select("""SELECT quality FROM date_%s WHERE user_id = '%d' and word_id = '%d' and quality IS NOT NULL """ % (curr_table, c.message.chat.id, word_id)) 
                    if len(result) != 0:
                        for (item,) in result:
                            quality = json.loads(item)
                            break 

                buttons_time, buttons_caption = calculate_buttons(quality)
                scores = [0,2,3,4,5]
                but_list = []
                key = types.InlineKeyboardMarkup()
                for idx in range(len(buttons_time)):
                    if buttons_time[idx] != None:
                        c_d = ''.join(['Interval', ';', str(buttons_time[idx]), ';', str(word_id), ';', str(scores[idx]), '|', curr_table])
                        but_list.append(types.InlineKeyboardButton(text=buttons_caption[idx], callback_data=c_d))
                key.add(*but_list) 

                result = db_select("""SELECT * FROM %s WHERE id = '%d' """ % (curr_table, word_id))
                for res in result:
                    if len(res) == 11:
                        english = re.sub('{{\w*::\w*}}', res[4], res[3])
                        bot.edit_message_text(chat_id=c.message.chat.id, message_id=c.message.message_id, text=english, reply_markup = '')
                        keybt = types.ReplyKeyboardMarkup(one_time_keyboard = True, row_width=1, resize_keyboard=True)
                        bot.send_voice(c.message.chat.id, caption = res[4] + '\n' + res[5] + '\n' + res[6], voice=open(path+res[7], 'rb'), reply_markup=key)
                        break


        if 'Interval' in call_back_data or call_back_data == "Study":
            if curr_table in users_info[c.message.chat.id]:
                quality = []
                if 'Interval' in call_back_data:
                    _, interval, word_id, score = call_back_data.split(';')
                    word_id = int(word_id)
                    interval = int(interval)
                    score = int(score)

                    if word_id != None:
                        result = db_select("""SELECT quality FROM date_%s WHERE user_id = '%d' and word_id = '%d' and quality IS NOT NULL """ % (curr_table, c.message.chat.id, word_id)) 
                        if len(result) != 0:
                            for (item,) in result:
                                quality = json.loads(item)
                                break 

                    quality.append(score)
                    print('curr_time =', curr_time)
                    db_edit('execute', """UPDATE date_%s SET quality = '%s', date = '%d' WHERE user_id = '%d' and word_id = '%d' """ % (curr_table, json.dumps(quality), get_next_date(interval, users_info[c.message.chat.id]['time_zone']), c.message.chat.id, word_id))                 
                else:
                    word_id = None

                word_set = users_info[c.message.chat.id][curr_table]

                if word_id != None:        
                    for key in ['new','learning','to_review']:
                        if word_id in word_set[key]:
                            if key == 'new':
                                word_set['learned_today'] += 1
                            word_set[key].remove(word_id)
                    if score < 3 or (score == 4 and interval == 10):
                        word_set['learning'].append(word_id)
                    db_edit('execute', """UPDATE users SET %s = '%s' WHERE user_id = '%d' """ % (curr_table, json.dumps(word_set), c.message.chat.id))

                word_id = None
                if len(word_set['learning']) != 0: 
                    if len(word_set['new']) == 0 and len(word_set['to_review']) == 0:
                        word_id = word_set['learning'][0]
                    else:          
                        result = db_select("""SELECT date FROM date_%s WHERE user_id = '%d' and word_id = '%d' and date < '%d' """ % (curr_table, c.message.chat.id, word_set['learning'][0], curr_time)) 
                        if len(result) != 0:
                            word_id = word_set['learning'][0]                          
                if len(word_set['new']) != 0 and word_id == None:
                    word_id = word_set['new'][0]
                if len(word_set['to_review']) != 0 and word_id == None:
                    word_id = word_set['to_review'][0]

                if word_id != None:
                    result = db_select("""SELECT * FROM %s WHERE id = '%d' """ % (curr_table, word_id))
                    for res in result:
                        if len(res) == 11:
                            key = types.InlineKeyboardMarkup()
                            c_d = ''.join(['Show_answer', ';', str(word_id), '|', curr_table])

                            but_1 = types.InlineKeyboardButton(text='Показать ответ', callback_data=c_d)
                            key.add(but_1)

                            bot.edit_message_reply_markup(c.message.chat.id, message_id = c.message.message_id, reply_markup = '')
                            english = re.sub('{{\w*::\w*}}', '[...]', res[3])
                            bot.send_photo(c.message.chat.id, photo=open(path+res[2], 'rb'))
                            bot.send_message(c.message.chat.id, '🌐' + str(len(word_set['new'])) + '🔵' + str(len(word_set['learning'])) + '🔴' + str(len(word_set['to_review'])) + '\n' + '#' + str(res[0]) + '\n' + english + '\n\nВведите пропущенное слово:', reply_markup=key)
                            users_info[c.message.chat.id]['user_reply'] = True
                            users_info[c.message.chat.id]['curr_table'] = curr_table
                            users_info[c.message.chat.id]['word_id'] = word_id
                            break
                else:
                    bot.send_message(c.message.chat.id, "Ура! На сегодня всё.")   
                users_info[c.message.chat.id][curr_table] = word_set



bot.polling(none_stop=True)
