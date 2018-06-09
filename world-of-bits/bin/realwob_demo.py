#!/usr/bin/env python
from pprint import pprint
import sys
import os
import realwob.db.sqlite as sqlite
import realwob.db.redisdb as redisdb
import re
import json
import shutil
import numpy as np

from realwob.db import KeyValueStore

if len(sys.argv) < 3:
    print('Usage: ./bin/realwob_demo.py [command] [env_id]')
    exit(1)

command = sys.argv[1]
env_id = sys.argv[2]
demo_path = 'data/demo'
if len(sys.argv) == 4:
    db_path = sys.argv[3]
    kv_store = KeyValueStore(db_path)
else:
    db_path = None
    kv_store = None

def unzip_demo(root):
    for demonstrator_id in os.listdir(root):
        print('unzip demonstrator_id = {}'.format(demonstrator_id))
        if demonstrator_id.startswith('.') or demonstrator_id.startswith('__'):
            continue
        demonstrator_path = os.path.join(root, demonstrator_id)
        for demo_id in os.listdir(os.path.join(root, demonstrator_id)):
            if demo_id.endswith('.tar.gz'):
                os.system('tar -xvf {} -C {}'.format(os.path.join(demonstrator_path, demo_id),
                                                  demonstrator_path))

def clean_demo(root):
    for demonstrator_id in os.listdir(root):
        if demonstrator_id.startswith('.') or demonstrator_id.startswith('__'):
            continue
        demonstrator_path = os.path.join(root, demonstrator_id)
        for demo_id in os.listdir(os.path.join(root, demonstrator_id)):
            print('cleaning demon {}/{}'.format(demonstrator_id, demo_id))
            demo_path = os.path.join(demonstrator_path, demo_id)
            if os.path.exists(demo_path) and os.path.isdir(demo_path):
                valid_demo = False
                with open(os.path.join(demo_path, 'rewards.demo'), 'r') as f:
                    #events_text = f.read()
                    #if re.findall(r'env\.text(?:.|\n)*resetting', events_text):
                    #    continue
                    #else:
                    #    print(events_text)
                    lines = f.readlines()
                    env_text = 0
                    env_state = None
                    for line in lines:
                        try:
                            event = json.loads(line)
                        except json.decoder.JSONDecodeError as e:
                            print('[error] Cannot decode JSON {}'.format(str(e)))
                            print('\t line = {}'.format(line))
                        message = event.get('message')
                        if not message:
                            continue
                        if 'env.text' in message.get('method'):
                            env_text +=1
                        if 'env.describe' in message.get('method'):
                            env_state = message['body'].get('env_state')
                        if env_state == 'resetting' and env_text > 0:
                            valid_demo = True
                if not valid_demo:
                    print('- Not a valid demo {}'.format(demo_path))
                    shutil.rmtree(demo_path)
            elif demo_path.endswith('.tar.gz'):
                print('- Remove tar.gz file {}'.format(demo_path))
                os.remove(demo_path)
        if not os.listdir(demonstrator_path):
            os.removedirs(demonstrator_path)


def stat_demo(root):
    global kv_store
    global env_id

    all_episodes = []
    for demonstrator_id in os.listdir(root):
        if demonstrator_id.startswith('.') or demonstrator_id.startswith('__'):
            continue
        demonstrator_path = os.path.join(root, demonstrator_id)
        for demo_id in os.listdir(os.path.join(root, demonstrator_id)):
            episodes = []
            demo_path = os.path.join(demonstrator_path, demo_id)
            if os.path.exists(demo_path) and os.path.isdir(demo_path):
                with open(os.path.join(demo_path, 'rewards.demo'), 'r') as f:
                    lines = f.readlines()
                    episode_start = False
                    episode = {}
                    last_time = None
                    for line in lines:
                        try:
                            event = json.loads(line)
                        except json.decoder.JSONDecodeError as e:
                            print('[error] Cannot decode JSON {}'.format(str(e)))
                            print('\t line = {}'.format(line))
                        message = event.get('message')
                        if not message:
                            continue
                        if 'env.text' in message.get('method') and 'instruction' in message['body']['text']:
                            episode['start'] = event['timestamp']
                            episode['instruction'] = message['body']['text']['instruction']
                            if kv_store:
                                episode['POST'] = kv_store[json.dumps(episode['instruction'])]
                        if 'env.describe' in message.get('method'):
                            env_state = message['body'].get('env_state')
                            if env_state == 'resetting' and episode.get('start'):
                                episode['end'] = event['timestamp']
                                episode['time'] = episode['end'] - episode['start']
                                episode['demonstrator_id'] = demonstrator_id
                                episode['demo_id'] = demo_id
                                episode['env_id'] = env_id
                                episodes.append(episode)
                                episode = {}
                        if 'timestamp' in event:
                            last_time = event['timestamp']
                all_episodes.extend(episodes)
    pprint(all_episodes)
    print('----------------------------------------------')
    print('num of episodes = ', len(all_episodes))
    print('average time length = ', np.mean([episode['time'] for episode in all_episodes]))



if command == 'sync':
    os.system('./bin/sync_demo.sh {}'.format(env_id))
elif command == 'unzip':
    unzip_demo(os.path.join(demo_path, env_id))
elif command == 'clean':
    clean_demo(os.path.join(demo_path, env_id))
elif command == 'stat':
    stat_demo(os.path.join(demo_path, env_id))
else:
    raise ValueError('unrecognized command {}'.format(command))
