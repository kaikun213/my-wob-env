import logging
import re
import sqlite3
import threading
import json
import random
import math
import urllib
import os

from mitmproxy.utils import strutils

from realwob.db import KeyValueStore

logger_name = 'wob_rewarder'
logger = logging.Logger(logger_name)
log_warn = lambda msg, *args, **kwargs: logger.warn('\033[94m [wob_rewarder] %s \033[0m' % msg, *args, **kwargs)
log_info = lambda msg, *args, **kwargs: logger.info('\033[94m [wob_rewarder] %s \033[0m' % msg, *args, **kwargs)
logger.setLevel(logging.INFO)

def get_flow_url(flow):
    request = flow.request
    _, netloc, path, _, query, _ = urllib.parse.urlparse(request.url)
    return netloc + path


def parse_webform(flow):
    r = flow.request

    _, netloc, path, _, query, _ = urllib.parse.urlparse(r.url)
    # these parameters will be ignored during matching.
    to_bytes = lambda params: [strutils.always_bytes(i) for i in params]

    queriesArray = urllib.parse.parse_qsl(query, keep_blank_values=True)

    headers = dict(r.data.headers)

    form_items = []
    # matches json-type responses. for example,
    # application/json;charset=UTF-8
    # application/xxx-json.
    content_type = (headers.get('content-type', '') or
                    headers.get('Content-Type', ''))
    if re.match(r'application/.*json.*', content_type):
        form_unsored = json.loads(r.data.content.decode('utf-8'))
        form_items = [(k, json.dumps(form_unsored[k], sort_keys=True))
                        for k in sorted(form_unsored.keys())]
    else:
        form_contents = r.urlencoded_form or r.multipart_form
        log_warn('form contents = %s', form_contents)
        if form_contents:
            form_items = form_contents.items(multi=True)

    form = dict(form_items)
    return form


class WebRewarder(object):
    ''' give instructions to agents, and reward based on two things:
            1. the http traffic produced by agent behavior
            2. DOM elements
    '''
    def __init__(self):
        self._lock = threading.Lock()
        WebRewarder.reset(self)

    def reset(self):
        self._lock.acquire()
        self._done = False
        self._instruction = ''
        self._lock.release()

    def done(self):
        self._lock.acquire()
        self._done = True
        self._lock.release()

    def close(self):
        return

    @property
    def instruction(self):
        return self._instruction

    @instruction.setter
    def instruction(self, new_instruction):
        'ignore set_insruction'
        return

    def observe_flow(self, flow):
        ''' observe requests to server '''
        return (0., False)

    def init_browser(self, browser):
        return

    def observe_browser(self, browser):
        return (0., False)


class WebImitateRewarder(WebRewarder):
    def __init__(self, name, mode='DATA'):
        '''
        if mode is 'DATA', then the rewarder records instructions and traffic.
        if mode is 'ENV', then the rewarder randomly chooses instrutions from DB,
            and rewards the agent if expected traffic is produced.
        '''
        super(WebImitateRewarder, self).__init__()
        self.db_scope = 'rewarder.imitate.' + name
        self.db = KeyValueStore(self.db_scope)
        # reset env
        self.mode = mode
        WebImitateRewarder.reset(self)

    def reset(self):
        ''' reset rewarder state '''
        super(WebImitateRewarder, self).reset()
        if self.mode == 'DATA':
            self._instruction = {}
            self._requests = {}
        elif self.mode == 'ENV':
            instruction_all = list(self.db.keys())
            log_warn('[wob_rewarder] all instructions = %s', instruction_all)
            instruction_index = random.randint(0, len(instruction_all) - 1)
            raw_instruction_json = instruction_all[instruction_index]
            log_warn('raw json %s', raw_instruction_json)
            instruction_json = raw_instruction_json.decode('utf-8')
            self._instruction = json.loads(instruction_json)
            self._requests = self.db[instruction_json]
            log_warn('[pick env] %s %s', self._instruction, self._requests)
        else:
            raise ValueError('unrecognized mode {}'.format(self.mode))

    def save(self):
        ''' save (instruction, traffic) pair to db '''
        instruction_json = json.dumps(self._instruction, sort_keys=True)
        logger.warn('%s', str(self._requests))
        logger.warn('%s', str(instruction_json))
        self.db[instruction_json] = self._requests

    def close(self):
        log_warn('closing the rewarder db')
        self.save()

    @property
    def instruction(self):
        return self._instruction

    @instruction.setter
    def instruction(self, new_instruction):
        self._instruction = new_instruction

    def add_request(self, url, request):
        if url not in self._requests:
            self._requests[url] = []
        self._requests[url].append(request)
        self.save()
        log_warn('[request added] %s %s', url, str(request))

    def requests_of_interest(self, flow):
        ''' ROI - request of interest - a function to be implemented.
            if the request is of interest, it is meaningful and will be used as
                part of the reward calculation.
            Example: submit POST request to flight booking websites.

            Return
                a list of ROIs.
                if ROI is not found, return []
        '''
        return []

    def observe_data(self, flow):
        ''' observe function in DATA mode.
        '''
        rois = self.requests_of_interest(flow)
        if not rois:
            return

        log_warn('[observe_env] %s', flow)
        request = flow.request
        url = get_flow_url(flow)

        for roi in rois:
            self.add_request(url, roi)

    def observe_env(self, flow):
        ''' observe function in ENV mode
            return a pair (reward, done)
        '''
        rois = self.requests_of_interest(flow)
        if not rois:
            return (0., False)

        log_warn('[observe_env] %s', flow)
        request = flow.request
        url = get_flow_url(flow)

        gold_requests = self._requests.get(url, [])
        # compute score, which uses F1 metric.
        reward = 0.
        for roi in rois:
            total_match = 0.
            total_pred = 0.
            total_gold = 0.
            log_warn('[roi] %s', str(roi))
            for gold_request in gold_requests:
                # compute partial credit.
                log_info('[gold_request] %s', str(gold_request))
                for param in gold_request:
                    if param in roi and roi[param] == gold_request[param]:
                        total_match += 1.
                total_gold += len(gold_request)
            total_pred += len(roi)
            prec = total_match / total_pred
            if total_gold == 0: # we don't have any gold requests.
                reward += 0
            else:
                recall = total_match / total_gold
                f1 = 2 * prec * recall / (prec + recall)
                reward += f1
        self._lock.acquire()
        _done = self._done
        self._done = False
        self._lock.release()
        log_warn('[observe_env] reward=%d done=%s', reward, str(_done))
        return (reward, _done)

    def observe_flow(self, flow):
        ''' return a pair (reward, done) '''
        if self.mode == 'DATA':
            self.observe_data(flow)
            self._lock.acquire()
            _done = self._done
            self._done = False
            self._lock.release()
            return (0., _done)
        elif self.mode == 'ENV':
            return self.observe_env(flow)
        else:
            raise ValueError('unrecognized mode {}'.format(self.mode))



class DOMClickButtonRewarder(WebRewarder):
    def __init__(self, selector, prescript=''):
        self.selector = selector
        self.prescript = prescript

    def init_browser(self, browser):
        self.browser = browser

    def reset(self):
        super(DOMClickButtonRewarder, self).reset()
        logger.warn('execute script %s', self.prescript)
        self._button_text = self.browser.execute_script(
            self.prescript +
            "WOB_REWARD_GLOBAL = 0.;"
            "WOB_DONE_GLOBAL = false;"
            # disable all clickable elements.
            "var disable_clicks = function(e) {e.stopPropagation(); e.preventDefault()};"
            "for(var ele of document.querySelectorAll('*')) {ele.addEventListener('click', disable_clicks, true)};"
            # set a button as target.
            "var WOB_BUTTONS = [];"
            "for(var btn of document.querySelectorAll('%s')) { if(btn.innerText.length > 0) WOB_BUTTONS.push(btn);};"
            "var btn_idx = Math.floor(Math.random() * WOB_BUTTONS.length);"
            "var wob_button = WOB_BUTTONS[btn_idx];"
            "var x = wob_button; while(x) {x.removeEventListener('click', disable_clicks, true); x = x.parentNode; }"
            "wob_button.addEventListener('click', function(e) { WOB_REWARD_GLOBAL = 1.; WOB_DONE_GLOBAL = true; e.stopPropagation(); e.preventDefault();}, true);"
            "return wob_button.innerText;"  % self.selector
        )
        logger.warn('execute script done')
        self._instruction = 'Click \"' + self._button_text + '\"'

