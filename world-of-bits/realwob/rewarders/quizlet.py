import random
import re
import logging

from realwob.rewarders.utils import choose_one
from realwob.rewarders import (WebRewarder, get_flow_url, parse_webform,
                               log_warn, log_info)

class QuizletLearnRewarder(WebRewarder):
    def __init__(self, mode='DATA'):
        super(QuizletLearnRewarder, self).__init__()

    def observe_flow(self, flow):
        url = get_flow_url(flow)
        print('url', url)
        if url == 'quizlet.com/activity-log/create':
            return (0.1, False)
        return (0., False)

    def reset(self):
        super(QuizletLearnRewarder, self).reset()


