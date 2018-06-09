''' web navigation instructions.
    for signup forms, this includes "username", "password", ...
'''
import random


def _choose_one(items):
    index = random.randint(0, len(items) - 1)
    return items[index]


class UserProfileTemplate(object):
    usernames = ['tim', 'robert', 'root', 'admin', 'boss']
    passwords = ['openai', '123456', 'abcxyz']
    first_names = ['Tim', 'Robert', 'Root', 'Admin', 'John']
    last_names = ['Shi', 'Root', 'Admin']
    domains = ['openai.com', 'stanford.edu', 'mit.edu', 'gmail.com']

    def generate(self):
        username = _choose_one(self.usernames)
        domain = _choose_one(self.domains)
        first_name = _choose_one(self.first_names)
        last_name = _choose_one(self.last_names)
        full_name = first_name + ' ' + last_name
        password = _choose_one(self.passwords)
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

