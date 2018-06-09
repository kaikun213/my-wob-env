import argparse
import logging

from realwob import ProxyController
from realwob.rewarders.booking import KayakSubmitWebRewarder

logger = logging.Logger(name='realwob')
logger.setLevel(logging.INFO)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='WoB proxy parser')
    parser.add_argument('-m', '--mode', default='DATA')
    parser.add_argument('-v', action='count')
    args = parser.parse_args()

    kayak_rewarder = KayakSubmitWebRewarder()

    controller = ProxyController(mode=args.mode, cache_path='realwob/cache',
                                 rewarders=[kayak_rewarder])
    controller.run()  # run forever.
