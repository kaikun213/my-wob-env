import random
import re
import logging

from realwob.rewarders.utils import choose_one
from realwob.rewarders import (WebImitateRewarder, get_flow_url, parse_webform,
                               log_warn, log_info)

class UserProfileTemplate(object):
    usernames = ['alice', 'bob', 'charles', 'nell', 'tom']
    passwords = ['openai', '123456', 'abcxyz']
    first_names = ['Alice', 'Bob', 'Charles', 'Nell', 'Tom']
    last_names = ['Trump', 'Clinton', 'Smith', 'Johnson', 'Williams', 'Jones']
    domains = ['openai.com', 'stanford.edu', 'mit.edu', 'gmail.com']

    def generate(self):
        username = choose_one(self.usernames)
        domain = choose_one(self.domains)
        first_name = choose_one(self.first_names)
        last_name = choose_one(self.last_names)
        full_name = first_name + ' ' + last_name
        password = choose_one(self.passwords)
        email = username + '@' + domain
        phone = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        return {
            'username': username,
            'password': password,
            'password_again': password,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': full_name,
            'email': email,
            'email_again': email,
            'phone': phone
        }


def SignUpRewarderTemplate(_id):
    class SignUpRewarder(WebImitateRewarder):
        def __init__(self, db_path, mode='DATA'):
            super(SignUpRewarder, self).__init__(db_path, mode)

        def requests_of_interest(self, flow):
            url = get_flow_url(flow)

            # trigger RoI.
            log_warn('[RoI] triggered %s', url)
            if (flow.request.method == 'POST'
                and url == 'openai.github.io/signup-forms/{}/submit'.format(_id)):
                log_warn('[RoI] triggered %s', url)
                form = parse_webform(flow)
                self.done()
                log_warn('[RoI] parsed form = %s', str(form))
                return [form]

            # nothing is triggered.
            return []

        def reset(self):
            super(SignUpRewarder, self).reset()
            template = UserProfileTemplate()
            self._instruction = '\n'.join([':'.join((k, v))
                        for (k, v) in template.generate().items()])

    return SignUpRewarder

