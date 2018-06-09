#!/usr/bin/env python
import argparse
import logging
import os
import sys
import time
from universe import wrappers

import gym
import universe

# Try this out for now
gym.undo_logger_setup()

logger = logging.getLogger()
formatter = logging.Formatter('[%(asctime)s] %(message)s')
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)
logger.addHandler(handler)

if __name__ == '__main__':
    # You can optionally set up the logger. Also fine to set the level
    # to logging.DEBUG or logging.WARN if you want to change the
    # amount of output.
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description=None)
    parser.add_argument('-e', '--env_id', required=True, help='Which environment to run on.')
    parser.add_argument('-f', '--fps', type=float, default=60.0, help='Number of frames per second.')
    parser.add_argument('-r', '--remote', default='vnc://localhost+15899', help='The number of environments to create (e.g. -r 20), or the address of pre-existing VNC servers and rewarders to use (e.g. -r localhost:5900+15900,localhost:5901+15901.')
    parser.add_argument('-v', '--verbose', action='count', dest='verbosity', default=0, help='Set verbosity.')
    args = parser.parse_args()

    if args.verbosity == 0:
        logger.setLevel(logging.INFO)
    elif args.verbosity >= 1:
        logger.setLevel(logging.DEBUG)


    # Record episodes as we go
    episode_scores = []
    current_episode_score = 0.
    rewarded_during_current_episode = False
    while True:
        env = wrappers.Unvectorize(gym.make(args.env_id))

        # Jot down the env_id so the uploader can find it later
        env_id_file_dir = os.path.join(os.sep, 'tmp', 'demo')
        env_id_file_path = os.path.join(env_id_file_dir, 'env_id.txt')
        if not os.path.exists(env_id_file_dir):
            logger.info("[DemonstrationAgent] Creating directory %s", env_id_file_dir)
            os.makedirs(env_id_file_dir)
        with open(env_id_file_path,'w') as env_id_file:
            logger.info("[DemonstrationAgent] Writing env id to file %s", env_id_file_path)
            env_id_file.write(args.env_id)

        # Connect through our recording proxies
        env.configure(remotes=args.remote, fps=args.fps, observer=True)
        env.reset()

        logger.info("[DemonstrationAgent] Starting demonstration with remote=%s, your average score will be recorded below...", args.remote)

        # Record episodes as we go
        while True:
            action = []

            # Call step with no actions.
            observation, reward, done, info = env.step(action)

            current_episode_score += reward
            if done:
                if current_episode_score == 0.:
                    logger.info("[DemonstrationAgent] Closing env after episode, will recreate")
                    logger.info("[DemonstrationAgent] Scored 0 reward during this episode, discarding it")

                    if len(episode_scores) != 0:
                        logger.info("[DemonstrationAgent] Average score over {} episodes: {}".
                                    format(len(episode_scores), sum(episode_scores) / len(episode_scores)))

                else:
                    episode_scores.append(current_episode_score)
                    logger.info("[DemonstrationAgent] Scored {} reward during this episode.".format(current_episode_score))
                    logger.info("[DemonstrationAgent] Average score over {} episodes: {}".
                                format(len(episode_scores), sum(episode_scores)/len(episode_scores)))

                current_episode_score = 0.
                rewarded_during_current_episode = False
                break

        logger.info('Closing env after episode, will recreate')
        env.close()
        env = None
