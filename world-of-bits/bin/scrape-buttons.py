from __future__ import print_function
from pprint import pprint
import logging
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False);
import json
import os
from multiprocessing import Pool
import argparse

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from realwob import ProxyController


if __name__ == '__main__':
    parser = argparse.ArgumentParser('scrape sites with buttons')
    parser.add_argument('--sites', type=str, help='the txt file that contains a list of websites')
    parser.add_argument('--device', type=str, default='Apple iPhone 6')
    parser.add_argument('--output', type=str, default='output the dataset')
    parser.add_argument('--screenshot', type=str, default='')

    args = parser.parse_args()

    # start proxy server.
    server = ProxyController(mode='DATA',
                                    cache_path='/tmp/demo/realwob/db/button-world',
                                    rewarders=[])
    server.start()

    # launch chrome.
    chrome_options = webdriver.ChromeOptions()

    chrome_options.add_argument('--disable-application-cache')
    chrome_options.add_argument('--proxy-server=0.0.0.0:8888')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_experimental_option('mobileEmulation',
                                        {'deviceName': args.device})
    browser = webdriver.Chrome(chrome_options=chrome_options)

    with open(args.sites, 'r') as f:
        sites = f.readlines()
        sites = [site.replace('\n', '') for site in sites]

    button_map = {}
    for site_name in sites:
        site = 'http://' + site_name
        print('visiting site {}'.format(site))
        try:
            browser.set_page_load_timeout(30) # timeout seconds
            browser.get(site)
        except: # timeout.
            pass

        if args.screenshot:
            try:
                if not os.path.exists(args.screenshot):
                    os.makedirs(args.screenshot)
                browser.save_screenshot(os.path.join(os.getcwd(), args.screenshot, site_name + '.png'))
            except Exception as e:
                print('[error] {}'.format(str(e)))

        buttons = []
        button_eles = []
        xpath = """.//{}[not(ancestor::div[contains(@style,'display:none')]) and not(ancestor::div[contains(@style,'display: none')])]"""

        for element in ['button', 'a']:
            button_eles.extend(browser.find_elements_by_xpath(xpath.format(element)))

        for button_ele in button_eles:
            button = button_ele.text.strip()
            if (button and
                    not (button_ele.value_of_css_property('width') == 'auto'
                    and button_ele.value_of_css_property('height') == 'auto')):
                buttons.append(button)

        if buttons:
            print(buttons)
            button_map[site] = buttons
        else:
            print('cannot find buttons on {}'.format(site))

    browser.quit()

    print('writing dataset')
    with open(args.output, 'w') as f:
        json.dump(button_map, f)

    print('finished')



