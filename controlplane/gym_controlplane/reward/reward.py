import logging
import time

from universe import pyprofile
from gym_controlplane import error

logger = logging.getLogger(__name__)

class RewardFromScore(object):
    @classmethod
    def build(self, spec):
        spec = spec.copy()
        type = spec.pop('type', 'score')
        if type == 'average_score':
            return AverageScore(**spec)
        elif type == 'negative_score':
            return NegativeScore(**spec)
        elif type == 'score':
            return Score(**spec)
        else:
            raise error.Error('Invalid reward_type: %s', type)

class Score(object):
    """Sum of rewards is score: so each reward is the delta of scores.
    """
    def __init__(self, initial_score=None, allow_negative_rewards=True):
        self.initial_score = initial_score
        self.allow_negative_rewards = allow_negative_rewards
        self._last_score = None

    def reward(self, score, cur_time):
        if self._last_score is None:
            if self.initial_score is not None:
                logger.info('First score parsed: score=%s. Our hardcoded initial_score=%s', score, self.initial_score)
                self._last_score = self.initial_score
            else:
                logger.info('First score parsed: score=%s', score)
                self._last_score = score
                # Unless told otherwise, we assume that your initial score
                # isn't due to you (maybe the rewarder is just starting
                # now, or maybe the game keeps scores around even when
                # episodes reset), and you deserve no reward from it.
                return 0, RewardParser.EMPTY
        if self._last_score is not None:
            pyprofile.gauge('reward_parser.score.last_score', self._last_score)
        if not self.allow_negative_rewards and score < self._last_score:
            pyprofile.gauge('reward_parser.score.unexpected_negative_reward', score-self._last_score)
            return 0, RewardParser.UNKNOWN_SCORE

        delta = score - self._last_score
        self._last_score = score
        return delta, RewardParser.EMPTY

class NegativeScore(Score):
    """Sum of rewards is negative score: so each reward is the negative of
    the delta of scores."""
    def __init__(self, **kwargs):
        super(NegativeScore, self).__init__(allow_negative_rewards=True, **kwargs)

    def reward(self, score, cur_time):
        delta, info = super(NegativeScore, self).reward(score, cur_time)
        return -delta, info

class AverageScore(object):
    """Sum of rewards is the average score: so each reward is the delta of
    mean score to date.
    """
    def __init__(self, send_first_score=True):
        """
        reward is change of time weighted running average score
        """
        self.n = 0
        self.send_first_score = send_first_score

    def reward_first(self, s, t):
        # setup statistics to track and give optional first score as reward
        self.avg_s = s
        self.prev_avg_s = s
        self.prev_t = t
        self.total_t = 0
        if self.send_first_score:
            return s
        else:
            return 0

    def reward_second(self, s, t):
        # we don't know how long we were at first score so assume equal weight
        dt = t - self.prev_t
        self.avg_s = self.avg_s*0.5 + s*0.5
        r = self.avg_s - self.prev_avg_s
        self.total_t += dt
        self.prev_t = t
        self.prev_avg_s = self.avg_s
        return r

    def reward_rest(self, s, t):
        dt = t - self.prev_t
        self.avg_s = (self.avg_s*self.total_t + s*dt)/(self.total_t+dt)
        r = self.avg_s - self.prev_avg_s
        self.total_t += dt
        self.prev_t = t
        self.prev_avg_s = self.avg_s
        return r

    def reward(self, score, cur_time):
        if self.n == 0:
            r = self.reward_first(score, cur_time)
        elif self.n == 1:
            r = self.reward_second(score, cur_time)
        else:
            r = self.reward_rest(score, cur_time)
        self.n += 1
        # TODO: return more diagnostics?
        return r, RewardParser.EMPTY

class RewardParser(object):
    UNKNOWN_SCORE = {'reward_parser.score.unknown': True}
    EMPTY = {}

    def __init__(self, env_id, scorer, vexpect,
                 # provided in YAML config
                 reward_from_score=None,
                 nonzero_reward_timeout=None,
    ):
        self.env_id = env_id
        self.scorer = scorer
        self.vexpect = vexpect
        # By default, the total reward is the final game score. But we
        # also e.g. support getting rewards for the average parsed
        # score (such as miles per hour).
        self._reward_from_score_spec = reward_from_score or {}
        self.nonzero_reward_timeout = nonzero_reward_timeout
        self.reset()

    def subscription(self):
        subscription = []
        if self.vexpect is not None:
            gameover = self.vexpect.gameover_subscription
            if gameover is None:
                logger.info('No gameover subscription available; not narrowing subscription')
                return None
            subscription += gameover
        if self.scorer is not None:
            scorer = self.scorer.subscription
            if scorer is None:
                logger.info('No scorer subscription available; not narrowing subscription')
                return None
            subscription += scorer
        return subscription

    def reset(self):
        self._warned = False
        # Reset the scorer internal state (e.g. median filter)
        # TODO: make scorers stateless, move state to rewarder
        #
        # TODO: sort out the state in vexpect -- those need resetting
        if self.scorer is not None:
            self.scorer.reset()
        if self.vexpect is not None:
            self.vexpect.reset()
        self.reward_from_score = RewardFromScore.build(self._reward_from_score_spec)
        self._last_score_time = time.time()
        self._last_nonzero_reward_time = time.time()

    def _score(self, img):
        if self.scorer is None:
            return None
        with pyprofile.push('reward.parsing.score'):
            return self.scorer.score(img)

    def _gameover(self, img):
        if self.vexpect is None:
            return None, None
        with pyprofile.push('reward.parsing.gameover'):
            return self.vexpect.gameover(img)

    def score(self, img):
        score = self._score(img)
        # Always run the gameover detector. Could optimize this on a
        # game-by-game basis, but it's pretty cheap to run -- O(100us)
        gameover, _ = self._gameover(img)
        return score, gameover

    def reward(self, img):
        score, done = self.score(img)
        now = time.time()

        # See how long we're running without score, and error out if too long
        if done:
            logger.info('RESET CAUSE: gameover state reached')
        elif score is None:
            # If the scorer can't find anything and the episode isn't over,
            # we're probably stuck in some kind of weird or stale state.
            # It's been more than 100 seconds, we're done here.
            #
            # If no vexpect is provided, then we assume the user
            # is testing vexpect and will handle resets on their
            # own.
            if now > self._last_score_time + 70 and self.vexpect != None and self.scorer != None:
                pyprofile.incr('rewarder.reset.unable_to_parse_score_parse')
                logger.error('RESET CAUSE: Rewarder has been unable to parse a score since %.2f (%.2fs ago)', self._last_score_time, now-self._last_score_time)
                done = True
        else:
            # We got a good score, reset our timeout
            self._last_score_time = time.time()

        if score is None:
            # TODO: could return negative score here...
            return 0, done, self.UNKNOWN_SCORE

        reward_to_return, info = self.reward_from_score.reward(score, time.time())
        if reward_to_return == 0:
            if self.nonzero_reward_timeout is not None and \
               now - self._last_nonzero_reward_time > self.nonzero_reward_timeout:
                logger.error('RESET CAUSE: No non-zero rewards were generated since %.2f (%.2fs ago), which exceeds the configured timeout of %.2fs', self._last_nonzero_reward_time, now - self._last_nonzero_reward_time, self.nonzero_reward_timeout)
                done = True
        else:
            self._last_nonzero_reward_time = time.time()

        return reward_to_return, done, info

    def __repr__(self):
        return str(self)

    def __str__(self):
        return 'Reward<scorer={} vexpect={}>'.format(self.scorer, self.vexpect)
