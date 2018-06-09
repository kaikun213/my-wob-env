import logging
import os
import six
import yaml

from gym.utils import reraise
from gym_controlplane import error, integration, reward, utils

logger = logging.getLogger(__name__)

class DiskConfig(object):
    def __init__(self, id, config_path, vexpect_path):
        self.id = id
        self.config_path = config_path
        self.vexpect_path = vexpect_path

    def reward_parser_spec(self):
        scorer_spec = None
        reward_parser_spec = {}

        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                loaded = yaml.load(f)
            scorer_spec = loaded.get('scorer')
            reward_parser_spec = loaded.get('reward_parser', {})
        else:
            logger.error('No such config file: %s', self.config_path)

        vexpect_spec = None
        if os.path.exists(self.vexpect_path):
            vexpect_spec = self.vexpect_path
        else:
            logger.error('No such vexpect path: %s', self.vexpect_path)

        return scorer_spec, vexpect_spec, reward_parser_spec

    def build_reward_parser(self, load_vexpect=True, load_scorer=True):
        scorer_spec, vexpect_spec, reward_parser_spec = self.reward_parser_spec()
        if not load_scorer:
            logger.info('Not loading scorer, since load_scorer=%s (scorer_spec=%s). No rewards will be sent.', load_scorer, scorer_spec)
            scorer = None
        elif scorer_spec is not None:
            scorer = self._scorer(scorer_spec)
        else:
            # This is ok for development
            logger.error('No scorer configuration found for %s', self.id)
            scorer = None

        # Load vexpect
        if not load_vexpect:
            logger.info('Not loading vexpect, since load_vexpect=%s (vexpect_spec=%s). This means no gameover detection or initialization macro.', load_vexpect, vexpect_spec)
            vexpect = None
        elif vexpect_spec is not None:
            vexpect = integration.VExpect.load(vexpect_spec)
        else:
            logger.error('No vexpect configuration found for %s', self.id)
            vexpect = None

        reward_parser = reward.RewardParser(env_id=self.id, scorer=scorer, vexpect=vexpect, **reward_parser_spec)
        logger.info('Created reward parser for %s: %s', self.id, reward_parser)
        return reward_parser

    def _scorer(self, scorer):
        if scorer['type'] == 'DefaultScorer':
            loaded = reward.DefaultScorer(
                digits_path='{}/digits'.format(self.id),
                crop_coords=scorer['crop_coords'],
                digit_color=scorer['digit_color'],
                color_tol=scorer['color_tol'],
                min_overlap=scorer['min_overlap'],
                min_spacing=scorer['min_spacing'],
                max_spacing=scorer.get('max_spacing'))
        elif scorer['type'] == 'OCRScorerV0':
            loaded = reward.OCRScorerV0(
                model_path=scorer['model_path'],
                crop_coords=scorer['crop_coords'],
                prob_threshold=scorer['prob_threshold'],
                median_filter_size=scorer.get('median_filter_size'),
                max_delta=scorer.get('max_delta', None),
                )
        else:
            raise error.Error('Unsupported scorer type: {}'.format(scorer['type']))
        logger.info('Loaded scorer: %s', loaded)
        return loaded

class Task(object):
    # required props: self.id, self.config_path, self.vexpect_path

    def _disk_config(self):
        return DiskConfig(self.id, config_path=self.config_path, vexpect_path=self.vexpect_path)

    def reward_parser_spec(self):
        # TODO: dry this up?
        config = self._disk_config()
        return config.reward_parser_spec()

    def build_reward_parser(self, **kwargs):
        config = self._disk_config()
        parser = config.build_reward_parser(**kwargs)
        return parser

    def env_launcher(self, **kwargs):
        raise NotImplementedError

    def __str__(self):
        return '{}[{}]'.format(type(self).__name__, self.id)

    def __repr__(self):
        return str(self)

class Registry(object):
    def __init__(self):
        self._tasks = {}

        self._collections = {}
        self._default_collection = 'flashgames'
        self._default_env_launcher = None

    def register_task(self, id, task):
        self._tasks[id] = task

    def register_collection(self, name, srcdir, default_task):
        self._collections[name] = {
            'srcdir': srcdir,
            'default_task': default_task,
        }

    def register_defaults(self, env_launcher=None):
        self._default_env_launcher = env_launcher

    def env_launcher(self, spec, **kwargs):
        if spec is None and self._default_env_launcher is None:
            return None
        elif spec is None:
            return self._default_env_launcher(env_id=None, **kwargs)
        else:
            return spec.env_launcher(**kwargs)

    def spec(self, id):
        """Lazy loads a config if necessary"""
        id = id.strip()

        if id not in self._tasks:
            self._register_from_config_yaml(id)

        task = self._tasks[id]

        if 'deprecated' in task.tags:
            logger.warn('Retrieving deprecated task %s', task.id)
        return task

    def _register_from_config_yaml(self, id):
        if '.' in id:
            collection = id[:id.rfind('.')]
        elif self._default_collection is not None:
            collection = self._default_collection
        else:
            raise error.Error('Could not determine collection from ID, and no default_collection set: {}'.format(id))

        try:
            collection_info = self._collections[collection]
        except KeyError:
            raise error.UnregisteredCollection('Could not load requested id={}. That belongs to the {} collection, but this runtime supports {}. Perhaps that was a typo, or you meant to use a different runtime?'.format(id, collection, ', '.join(self._collections.keys())))
        srcdir = collection_info['srcdir']
        default_task = collection_info['default_task']

        path = os.path.abspath(os.path.join(srcdir, id, 'config.yml'))
        if not os.path.exists(path):
            raise error.UnregisteredEnv('Could not load spec for {}: no such file {}'.format(id, path), path)

        with open(path) as f:
            data = yaml.load(f)
        try:
            spec = data['spec']
        except KeyError:
            reraise(suffix='while examining data from {}'.format(path))
        constructor_name = spec.pop('type', default_task)
        constructor = utils.load(constructor_name)
        spec.pop('id', None)

        task = constructor(id=id, **spec)
        self._tasks[id] = task

registry = Registry()
spec = registry.spec
env_launcher = registry.env_launcher
register_task = registry.register_task
register_defaults = registry.register_defaults
register_collection = registry.register_collection
