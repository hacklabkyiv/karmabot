import gettext


class Status:
    OPEN = ':hourglass_flowing_sand:'
    CLOSED = ':white_check_mark:'


class Color:
    ERROR = '#FF0000'
    INFO = '#3AA3E3'


class Format:
    _INTERVALS = (604800,  # 60 * 60 * 24 * 7
                  86400,  # 60 * 60 * 24
                  3600,  # 60 * 60
                  60,
                  1)

    def __init__(self, lang, votes_up_emoji, votes_down_emoji, timeout):
        translate = gettext.translation(domain='messages', localedir='lang',
                                        languages=(lang,), fallback=True)
        translate.install()
        self._votes_up_emoji = votes_up_emoji
        self._votes_down_emoji = votes_down_emoji
        self._display_time = self.display_time(int(timeout))

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

        for i, count in enumerate(Format._INTERVALS):
            value = seconds // count
            if value:
                seconds -= value * count
                name = _('time').split()[i]
                result.append("{}{}".format(value, name))
        return ', '.join(result[:granularity])

    def hello(self):
        return Format.message(Color.INFO, _('hello'))

    def new_voting(self, username, karma):
        text = _('new_voting').format(Status.OPEN, karma, username,
                                      ':' + ': :'.join(self._votes_up_emoji) + ':',
                                      ':' + ': :'.join(self._votes_down_emoji) + ':',
                                      self._display_time)
        return Format.message(Color.INFO, text)

    def voting_result(self, username, karma, success):
        if success:
            emoji = ':tada:' if karma > 0 else ':face_palm:'
            text = _('voting_result_success').format(Status.CLOSED, username, karma, emoji)
        else:
            emoji = ':fidget_spinner:'
            text = _('voting_result_nothing').format(Status.CLOSED, username, emoji)

        return Format.message(Color.INFO, text)

    def report_karma(self, username, karma):
        return Format.message(Color.INFO, _('report_karma').format(username, karma))

    def parsing_error(self):
        return Format.message(Color.ERROR, _('parsing_error').format(':robot_face:'))

    def max_shot_error(self, max_shot):
        return Format.message(Color.ERROR, _('max_shot_error').format(max_shot))

    def strange_error(self):
        return Format.message(Color.ERROR, _('strange_error').format(':grimacing:'))

    def robo_error(self):
        return Format.message(Color.ERROR, _('robo_error').format(':robot_face:'))

    def cmd_error(self):
        return Format.message(Color.ERROR, _('cmd_error'), image='https://i.imgflip.com/2cuafm.jpg')
