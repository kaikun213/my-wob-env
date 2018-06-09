import logging
import numpy as np
import os
import re
import time

from PIL import Image

from universe import utils
from gym.utils import reraise
from gym_controlplane import error, reward

logger = logging.getLogger(__name__)

def write_png(target, contents, mode=None):
    contents = Image.fromarray(contents, mode=mode)
    contents.save(target, 'png')

class State(object):
    def __init__(self, state_name):
        self.state_name = state_name
        match = re.search('^(\w+)(\d+)$', state_name)
        if match:
            self.state_category = match.group(1)
            self.state_id = int(match.group(2))
        else:
            self.state_category = None
            self.state_id = None

    @classmethod
    def load(cls, src_dir, state_name, spec):
        spec = spec.copy()
        type = spec.pop('type')
        try:
            if type == 'ImageMatchState':
                return ImageMatchState(src_dir=src_dir, state_name=state_name, **spec)
            if type == 'MaskState':
                return MaskState.load(src_dir=src_dir, state_name=state_name, **spec)
            else:
                raise error.Error('Bad state type: {}'.format(type))
        except error.Error:
            raise
        except:
            reraise(suffix='(while applying: state_name={} spec={})'.format(state_name, spec))

class MaskMatcher(object):
    @classmethod
    def load(cls, name, mask_path, pixel_info_path):
        mask = np.array(Image.open(mask_path))
        # TODO figure out persistence
        pixel_info = np.array(Image.open(pixel_info_path))
        return cls(name, mask, pixel_info)

    def __init__(self, name, mask, pixel_info, count=None, match_threshold=None, warn_threshold=None):
        self.name = name
        if count is None: count = 10000
        self.count = count
        if match_threshold is None: match_threshold = 0.05
        self.match_threshold = match_threshold
        if warn_threshold is None: warn_threshold = 3 * match_threshold
        self.warn_threshold = warn_threshold

        self._mask = mask
        self._pixel_info = pixel_info

        # Set blacklisted pixels to infinity
        pixel_age = np.where((mask == 0).all(axis=2), np.inf, pixel_info['pixel_age'])
        pixel_age_flat = pixel_age.reshape(-1)
        # Order indices by recency. This will include all the np.infs
        all_pixels_infs = np.argsort(pixel_age_flat)
        # Slice off np.infs
        cutoff = np.searchsorted(pixel_age_flat[all_pixels_infs], np.inf, side='left')
        all_pixels = all_pixels_infs[:cutoff]

        # Grab the 10k pixels that are most recent identifiers of this state
        pixels = all_pixels[:count]

        self._mask_pixels = all_pixels
        self._fullmask_pixels = pixels

        # Build the fullmask. This contains only the 10k pixels we're
        # going to use for matching.
        self._fullmask_values = self._apply_fullmask_values(mask)
        self._fullmask = self._apply_fullmask(mask)

        if len(self._fullmask_pixels) == 0:
            logger.warn('WARNING: mask %s is empty', self.name)

        # # Diagnostics
        # offset = count
        # value = pixel_age_flat[all_pixels[offset]]
        # while offset < len(all_pixels) and pixel_age_flat[all_pixels[offset]] == value:
        #     offset += 1
        # (candidates, ) = np.where(pixel_age_flat != np.inf)
        # finite_only = pixel_age_flat[np.where(pixel_age_flat != np.inf)]
        # logger.info('state=%s offset=%s valid_total=%s total=%s histogram=%s', name, offset, len(candidates), len(pixel_age_flat), np.histogram(finite_only))

    def save(self, src_dir):
        mask_target = os.path.join(src_dir, '{}-mask.png'.format(self.name))
        write_png(mask_target, self._mask)

        fullmask_target = os.path.join(src_dir, '{}-fullmask.png'.format(self.name))
        write_png(fullmask_target, self._fullmask)

        pixel_age_target = os.path.join(src_dir, '{}-pixel-age.png'.format(self.name))
        write_png(pixel_age_target, self._pixel_info['pixel_age'], mode='I')

        mouse_distance_target = os.path.join(src_dir, '{}-mouse-distance.png'.format(self.name))
        write_png(mouse_distance_target, 100*self._pixel_info['mouse_distance'], mode='I')

        logger.info('%s: saving assets: mask=%s', self.name, mask_target)

    @classmethod
    def load_assets(cls, src_dir, state_name):
        mask = Image.open(os.path.join(src_dir, '{}-mask.png'.format(state_name)))
        fullmask = Image.open(os.path.join(src_dir, '{}-fullmask.png'.format(state_name)))
        pixel_age = Image.open(os.path.join(src_dir, '{}-pixel-age.png'.format(state_name)))
        mouse_distance = Image.open(os.path.join(src_dir, '{}-mouse-distance.png'.format(state_name)))

        return np.array(mask), np.array(fullmask), {
            'pixel_age': np.array(pixel_age),
            'mouse_distance': np.array(mouse_distance) / 100,
        }

    def _apply_fullmask(self, img):
        # Mostly for debugging
        fullmask_values = self._apply_fullmask_values(img)
        fullmask_flat = np.zeros(img.shape, dtype=np.uint8).reshape((-1, 3))
        fullmask_flat[self._fullmask_pixels] = fullmask_values
        return fullmask_flat.reshape(img.shape)

    def _apply_fullmask_values(self, img):
        return img.reshape((-1, 3))[self._fullmask_pixels]

    def _apply_mask(self, img):
        # Mostly for debugging
        mask_values = self._apply_mask_values(img)
        mask_flat = np.zeros(img.shape, dtype=np.uint8).reshape((-1, 3))
        mask_flat[self._mask_pixels] = mask_values
        return mask_flat.reshape(img.shape)

    def _apply_mask_values(self, img):
        return img.reshape((-1, 3))[self._mask_pixels]

    def match(self, target):
        masked = self._apply_fullmask_values(target)
        different = np.count_nonzero(self._fullmask_values != masked)
        distance = different/(3*len(self._fullmask_values))
        match = distance < self.match_threshold
        return match, {
            'distance': distance,
            'distance.warn': distance < self.warn_threshold,
            'mask.pixels': len(self._fullmask_values),
            'distance.match': match,
        }

    # Debug only
    def debug_masked(self, img):
        # Just what's actually seen by our filter
        masked = self._apply_mask(img)
        fullmasked = self._apply_fullmask(img)
        return masked, fullmasked

class MaskState(object):
    def __init__(self, state_name, mask, pixel_info, metadata=None, stage=None, delay=None, cooloff=None):
        self.state_name = state_name
        self.stage = stage
        self.mask_matcher = MaskMatcher(state_name, mask, pixel_info)
        self.metadata = metadata

        self.delay = delay
        self.cooloff = cooloff

        self.reset()

        self.subscription = None

    @property
    def match_threshold(self):
        return self.mask_matcher.match_threshold

    @classmethod
    def load(cls, src_dir, state_name, **spec):
        mask, fullmask, pixel_info = MaskMatcher.load_assets(src_dir=src_dir, state_name=state_name)
        return MaskState(state_name=state_name, mask=mask, pixel_info=pixel_info, **spec)

    def reset(self):
        # Mutable state
        self._last_active = 0

    def distance(self, screen):
        return self.mask_matcher.match(screen)

    def active(self, screen, elapsed):
        match, info = self.distance(screen)
        if self.delay is not None and self.delay > elapsed:
            if match:
                utils.periodic_log(self, 'state.delay', 'Though gameover matched for %s, state has not yet come online: delay=%s elapsed=%.2f', self, self.delay, elapsed)
            return False, info

        if match:
            delta = time.time() - self._last_active
            if self.cooloff is not None and delta < self.cooloff:
                if delta > 1:
                    # Not interesting for this to be active
                    # immediately after match, but interesting for it
                    # to remain active thereafter.
                    utils.periodic_log_debug(self, 'cooloff', '%s active but only %0.2f have passed (cooloff=%s)', self, delta, self.cooloff)
                return False, info

            self._last_active = time.time()
            return True, info
        else:
            return False, info

    def to_spec(self):
        spec = {
            'type': 'MaskState',
        }
        if self.stage is not None: spec['stage'] = self.stage
        if self.metadata is not None: spec['metadata'] = self.metadata
        if self.delay is not None: spec['delay'] = self.delay
        if self.cooloff is not None: spec['cooloff'] = self.cooloff
        return spec

    def save(self, src_dir):
        # Everything else is persisted in the spec, which is written
        # directly by VExpect
        self.mask_matcher.save(src_dir)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '{}<{}>'.format(type(self).__name__, self.state_name)

    def debug_show_expect(self):
        img = self.mask_matcher._fullmask
        src = np.array(img)
        self.debug_show(src, 'template for ')

    def debug_show(self, screen, prefix=''):
        masked, fullmasked = self.mask_matcher.debug_masked(screen)
        Image.fromarray(self.mask_matcher._fullmask).show()
        Image.fromarray(fullmasked).show()

        # chop = (self.mask_matcher._mask == 0).all(axis=2)[:, :, np.newaxis]
        # chop = np.broadcast_to(chop, self.mask_matcher._mask.shape)
        # manual_mask = np.where(chop, 255, screen).astype(np.uint8)
        # Image.fromarray(manual_mask).show()
        # import ipdb;ipdb.set_trace()

class ImageMatchState(State):
    def __init__(self, src_dir, state_name, image_name, stage=None, crop_coords=None, match_threshold=None, warn_threshold=None, delay=None, cooloff=None, autoactive=None):
        super(ImageMatchState, self).__init__(state_name)
        self.src_dir = src_dir

        self.stage = stage
        self.image_name = image_name
        self.crop_coords = crop_coords
        self.match_threshold = match_threshold
        self.warn_threshold = warn_threshold
        self.delay = delay
        self.autoactive = autoactive
        self.cooloff = cooloff
        self.match_image = None
        if src_dir is not None:
            # Allow missing image files -- often happens when people
            # delete extra images from disk (to avoid checking them
            # in) but don't bother removing from the vexpect.yml.
            self.image_path = os.path.join(src_dir, image_name)
            self.match_image = reward.MatchImage(self.image_path, crop_coords, match_threshold, warn_threshold)

        self.reset()
        self.subscription = [self.crop_coords]

    def reset(self):
        # Mutable state
        self._last_active = 0
        if self.match_image is not None:
            self.match_image.reset()

    def debug_crop(self, screen):
        cropped = reward.crop(screen, self.crop_coords)
        Image.fromarray(cropped).show()

    def debug_show_expect(self):
        logger.info('Showing the expected template: %s', self.image_path)
        img = Image.open(self.image_path)
        src = np.array(img)
        self.debug_crop(src)

    def debug_show(self, screen):
        self.debug_show_expect()
        self.debug_crop(screen)

    def distance(self, screen):
        info = {}
        distance = self.match_image.distance(screen)
        # Report the actual distance
        info['distance'] = distance
        info['distance.match'] = distance < self.match_image.match_threshold
        info['distance.warn'] = not info['distance.match'] and distance < self.match_image.warn_threshold
        return info['distance.match'], info

    def active(self, screen, elapsed):
        match, info = self.distance(screen)
        if self.delay is not None and self.delay > elapsed:
            if match:
                utils.periodic_log(self, 'state.delay', 'Though gameover matched for %s, state has not yet come online: delay=%s elapsed=%.2f', self, self.delay, elapsed)
            return False, info

        if match:
            delta = time.time() - self._last_active
            if self.cooloff is not None and delta < self.cooloff:
                if delta > 1:
                    # Not interesting for this to be active
                    # immediately after match, but interesting for it
                    # to remain active thereafter.
                    utils.periodic_log_debug(self, 'cooloff', '%s active but only %0.2f have passed (cooloff=%s)', self, delta, self.cooloff)
                return False, info

            self._last_active = time.time()
            return True, info
        else:
            return False, info

    def to_spec(self):
        spec = {
            'type': 'ImageMatchState',
            'image_name': self.image_name,
            'crop_coords': self.crop_coords,
        }
        if self.match_threshold is not None: spec['match_threshold'] = self.match_threshold
        if self.warn_threshold is not None: spec['warn_threshold'] = self.warn_threshold
        if self.delay is not None: spec['delay'] = self.delay
        if self.cooloff is not None: spec['cooloff'] = self.cooloff
        if self.stage is not None: spec['stage'] = self.stage
        if self.autoactive is not None: spec['autoactive'] = self.autoactive
        return spec

    def __repr__(self):
        return str(self)

    def __str__(self):
        return self.state_name
