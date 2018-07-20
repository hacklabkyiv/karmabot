_ = {
    'en': {
        'hello': """Hi! I\'m *karmabot*. You can do: 
- In any public channel 
    `@karmabot @username +++ blah blah` 
    If the most of you agree, the username will get a karma. Nothing will happen in any other case.

- In direct messages with bot:
    - `get @username` - get karma value for `username`
    - `set @username <KARMA>` - set karma value for `username`
    - `digest` - show users' karma in descending order (zero karma is skipped)
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
    - `digest` - показать карму пользователей в нисходящем порядке (нулевая опускается)
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

_INTERVALS = (604800,  # 60 * 60 * 24 * 7
              86400,   # 60 * 60 * 24
              3600,    # 60 * 60
              60,
              1)


class Status:
    OPEN = ':hourglass_flowing_sand:'
    CLOSED = ':white_check_mark:'


class Color:
    ERROR = '#FF0000'
    INFO = '#3AA3E3'


class Format:
    def __init__(self, lang):
        self._messages = _.get(lang, 'en')

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

    def display_time(self, seconds, granularity=4):
        result = []

        for i, count in enumerate(_INTERVALS):
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = self._messages['time'].get('one')[i]
                else:
                    name = self._messages['time'].get('many')[i]
                result.append("{} {}".format(value, name))
        return ', '.join(result[:granularity])

    def hello(self):
        return Format.message(Color.INFO, self._messages['hello'])

    def new_voting(self, username, karma, votes_up_emoji, votes_down_emoji, timeout):
        text = self._messages['new_voting'].format(Status.OPEN,
                                            karma,
                                            username,
                                            ':' + ': :'.join(votes_up_emoji) + ':',
                                            ':' + ': :'.join(votes_down_emoji) + ':',
                                            self.display_time(int(timeout)))
        return Format.message(Color.INFO, text)

    def voting_result(self, username, karma, success):
        if success:
            emoji = ':tada:' if karma > 0 else ':face_palm:'
            text = self._messages['voting_result_success'].format(Status.CLOSED, username, karma, emoji)
        else:
            emoji = ':fidget_spinner:'
            text = self._messages['voting_result_nothing'].format(Status.CLOSED, username, emoji)

        return Format.message(Color.INFO, text)

    def report_karma(self, username, karma):
        return Format.message(Color.INFO, self._messages['report_karma'].format(username, karma))

    def parsing_error(self):
        return Format.message(Color.ERROR, self._messages['parsing_error'].format(':robot_face:'))

    def max_shot_error(self, max_shot):
        return Format.message(Color.ERROR, self._messages['max_shot_error'].format(max_shot))

    def strange_error(self):
        return Format.message(Color.ERROR, self._messages['strange_error'].format(':grimacing:'))

    def robo_error(self):
        return Format.message(Color.ERROR, self._messages['robo_error'].format(':robot_face:'))

    def cmd_error(self):
        return Format.message(Color.ERROR, self._messages['cmd_error'], image='https://i.imgflip.com/2cuafm.jpg')
