from __future__ import print_function
from pprint import pprint
import logging
import sys
import json
from urlparse import urlparse, parse_qs
from multiprocessing import Pool

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import argparse


browser = webdriver.Chrome()
all_links = []

for _id in range(1, 100):
    browser.get('https://www.quantcast.com/top-mobile-sites/US/{}'.format(_id))

    elements = browser.execute_script("""return document.querySelectorAll('td.link')""")
    links = [ele.text.strip() for ele in elements]
    links = [link for link in links if link != 'Hidden profile']
    if not links:
        break
    all_links.extend(links)

with open('top-mobile-sites.txt', 'w') as f:
    for link in all_links:
        f.write(link + '\n')
