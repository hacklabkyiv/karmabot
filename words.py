_ = {
    'en': {
        'hello': """Hi! I\'m *karmabot*. You can do: 
- In any public channel 
    `@karmabot @username +++ blah blah` 
    If the most of you agree, the username will get a karma. Nothing will happen in any other case.

- In direct messages with bot:
    - `get @username` - get karma value for `username`
    - `set @username <KARMA>` - set karma value for `username`
    - `help` - show this message
    - `config` - show config for this execution""",
#############
        'new_voting': """{} *A new voting for {:+d} karma for user @{}*
 You can vote using emoji for that or initial message.
 _FOR:_ {}
 _AGAINST_: {}
 Other emoji will be ignored. The voting will be *{}* long from now""",
#############
        'voting_result_success': """{} *The voting is finished*
@{} receives {:+d} karma {}""",
#############
        'voting_result_nothing': """{} *The voting is finished*
@{} receives nothing {}""",
#############
        'report_karma': '@{}: {} karma',
#############
        'parsing_error': """Сould not calculate what the fuck one has typed there {}
A request for karma change should be like `@karmabot @username +++ blah blah`""",
#############
        'max_shot_error': 'Max damage is {} karma',
#############
        'strange_error': 'This, at least, looks strange {}',
#############
        'robo_error': 'Robots can also be offended {}',
#############
        'cmd_error': 'One does not simply handle a command',
#############
        'time': {'many': ('weeks', 'days', 'hours', 'minutes', 'seconds'),
                 'one': ('week', 'day', 'hour', 'minute', 'second')},
    },

    'ru': {
        'hello': """Привет! Я *karmabot*. Вы можете делать: 
- В любом публичном канале:
    `@karmabot @username +++ бла бла` 
    Если большинство согласно, username получит свое. В любом другом случае ничего не случится.

- В личных сообщениях с ботом:
    - `get @username` - получить карму `username`
    - `set @username <KARMA>` - установить новое значение кармы для `username`
    - `help` - показать это сообщение
    - `config` - показать конфиг для этого запуска
""",
#############
        'new_voting': """{} *Голосование за {:+d} кармы пользователю @{}* 
Голосовать нужно при помощи emoji к этому или оригинальному сообщению.
_ЗА:_ {}
_ПРОТИВ:_ {}
Остальные игнорируются. Голосование будет длиться *{}* с текущего времени""",
#############
        'voting_result_success': """{} *Голосование закончено*
@{} получает {:+d} кармы {}""",
#############
        'voting_result_nothing': """{} *Голосование закончено*
@{} ничего не получает {}""",
#############
        'report_karma': '@{}: {} кармы',
#############
        'parsing_error': """Не удалось вычислить шо там пописано {}
Запрос на изменение кармы должен быть типа `@karmabot @username +++ бла бла`""",
#############
        'max_shot_error': 'Максимальный урон {} кармы',
#############
        'strange_error': 'Это, как минимум, выглядит странно {}',
#############
        'robo_error': 'У роботов тоже есть чувства {}',
#############
        'cmd_error': 'Нельзя просто взять и обработать команду',
#############
        'time': {'many': ('недель', 'дней', 'часов', 'минут', 'секунд'),
                 'one': ('неделю', 'день', 'час', 'минуту', 'секунду')},
    }
}

MESSAGE = _['en']

_INTERVALS = (604800,  # 60 * 60 * 24 * 7
              86400,   # 60 * 60 * 24
              3600,    # 60 * 60
              60,
              1)


def display_time(seconds, granularity=4):
    result = []

    for i, count in enumerate(_INTERVALS):
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = MESSAGE['time'].get('one')[i]
            else:
                name = MESSAGE['time'].get('many')[i]
            result.append("{} {}".format(value, name))
    return ', '.join(result[:granularity])


def init(lang):
    r = _.get(lang, None)
    if r:
        global MESSAGE
        MESSAGE = r


class Status:
    OPEN = ':hourglass_flowing_sand:'
    CLOSED = ':white_check_mark:'


class Color:
    ERROR = '#FF0000'
    INFO = '#3AA3E3'


class Format:
    @staticmethod
    def message(color, text, image=None):
        return {
            'attachments': [{
                'mrkdwn_in': ['text'],
                'color': color,
                'attachment_type': 'default',
                'callback_id': 'karma_voting',
                "fallback": text,
                'text': text,
                'image_url': image
            }]
        }

    @staticmethod
    def hello():
        return Format.message(Color.INFO, MESSAGE['hello'])

    @staticmethod
    def new_voting(username, karma, votes_up_emoji, votes_down_emoji, timeout):
        text = MESSAGE['new_voting'].format(Status.OPEN,
                                            karma,
                                            username,
                                            ':' + ': :'.join(votes_up_emoji) + ':',
                                            ':' + ': :'.join(votes_down_emoji) + ':',
                                            display_time(int(timeout)))
        return Format.message(Color.INFO, text)

    @staticmethod
    def voting_result(username, karma, success):
        if success:
            emoji = ':tada:' if karma > 0 else ':face_palm:'
            text = MESSAGE['voting_result_success'].format(Status.CLOSED, username, karma, emoji)
        else:
            emoji = ':fidget_spinner:'
            text = MESSAGE['voting_result_nothing'].format(Status.CLOSED, username, emoji)

        return Format.message(Color.INFO, text)

    @staticmethod
    def report_karma(username, karma):
        return Format.message(Color.INFO, MESSAGE['report_karma'].format(username, karma))

    @staticmethod
    def parsing_error():
        return Format.message(Color.ERROR, MESSAGE['parsing_error'].format(':robot_face:'))

    @staticmethod
    def max_shot_error(max_shot):
        return Format.message(Color.ERROR, MESSAGE['max_shot_error'].format(max_shot))

    @staticmethod
    def strange_error():
        return Format.message(Color.ERROR, MESSAGE['strange_error'].format(':grimacing:'))

    @staticmethod
    def robo_error():
        return Format.message(Color.ERROR, MESSAGE['robo_error'].format(':robot_face:'))

    @staticmethod
    def cmd_error():
        return Format.message(Color.ERROR, MESSAGE['cmd_error'], image='https://i.imgflip.com/2cuafm.jpg')
