import logging
import os
import numpy as np
from collections import deque
from copy import deepcopy

from universe import pyprofile
from gym_controlplane import utils

logger = logging.getLogger(__name__)

def color_threshold(img, color=[255, 255, 255], tolerance=256):
    return np.abs(img-color).sum(-1) < tolerance

def preprocess_digits(dir_path, digit_color, color_tol):
    """ loads and thresholds a directory of cropped digits """
    digits = np.asarray([utils.imread(os.path.join(dir_path, '{}.png'.format(n))) for n in range(10)])
    digits = color_threshold(digits, color=digit_color, tolerance=color_tol)
    return digits

def resize(img):
    import cv2
    ratio = 16./img.shape[0]
    img = cv2.resize(img, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_AREA)
    return img

def crop(img, coords):
    if coords is not None:
        x, length, y, height = coords
        img = img[y:y+height, x:x+length]
    return img

def default_detection_to_score(detections):
    """ takes a list of digit detections and returns a numeric score"""
    if len(detections) > 0:
        return int(''.join([str(d) for d in detections]))
    else:
        return None

basedir = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../src'))

def path(*args):
    return os.path.join(basedir, *args)

class CropCache(object):
    def __init__(self, method, crop_coords, name):
        self.name = name
        self.crop_coords = crop_coords
        self.method = method

        self.reset()

    def reset(self):
        self._last_img = None
        self._last_value = None

    def get(self, cropped):
        if self._last_img is None:
            return

        match = np.array_equal(self._last_img, cropped)
        if match:
            pyprofile.incr('score.crop_cache.hit.{}'.format(self.name))
            return self._last_value
        else:
            self._last_img = None

    def put(self, cropped, value):
        self._last_img = cropped.copy()
        self._last_value = value

    def __call__(self, img):
        cropped = crop(img, self.crop_coords)
        with pyprofile.push('score.crop_cache.get.{}'.format(self.name)):
            value = self.get(cropped)
        if value is None:
            with pyprofile.push('score.crop_cache.readthrough.{}'.format(self.name)):
                value = self.method(cropped)
            self.put(cropped, value)
        return value

class DefaultScorer(object):
    def __init__(self,
            digits_path,
            crop_coords,
            digit_color=[255, 255, 255],
            color_tol=64,
            min_overlap=0.95,
            min_spacing=6,
            max_spacing=None,
            detection_to_score=default_detection_to_score
        ):
        """
        Crops and thresholds images and does pixel overlap on a left-right scan to find digits
        """
        if max_spacing is None:
            max_spacing = np.inf

        digits_path = path(digits_path)

        self.crop_coords = crop_coords
        self.digit_color = digit_color
        self.color_tol = color_tol
        self.min_overlap = min_overlap
        self.min_spacing = min_spacing
        self.max_spacing = max_spacing
        self.detection_to_score = detection_to_score

        self.digits = preprocess_digits(digits_path, digit_color, color_tol)
        self.digits_h, self.digits_w = self.digits.shape[1:3]
        self.digits_size = float(self.digits_h*self.digits_w)

        self._score = CropCache(self._score, self.crop_coords, 'OCRScorerV0')
        self.subscription = [self.crop_coords]

    def score(self, img):
        img = color_threshold(img, color=self.digit_color, tolerance=self.color_tol)
        h, w = img.shape
        last_i = -(self.min_spacing+1)
        detections = []
        for i in range(w-self.digits_w):
            patch = img[:, i:i+self.digits_w]
            pixel_overlap = (self.digits == patch).sum(1).sum(1)
            if np.max(pixel_overlap)/self.digits_size >= self.min_overlap:
                spacing = i - last_i
                if self.min_spacing <= spacing <= self.max_spacing:
                    detections.append(np.argmax(pixel_overlap))
                    last_i = i
        score = self.detection_to_score(detections)

    def reset(self):
        self.score.reset()

class OCRScorerV0(object):

    def __init__(self,
        model_path,
        crop_coords,
        detection_to_score=default_detection_to_score,
        prob_threshold=0.2,
        median_filter_size=None,
        max_delta=None,
        ):
        """
        ocr scorer - v0
        crops and then rescales image to 16 vertical pixels
        applies small vgg cnn to image to produce set of avg pool features
        applies a set of softmax decoders for each digit position
        greedy prediction over softmaxes
        averages ~4ms on openai macbook - 99th percentile ~7ms

        prob_threshold is the probability at which to drop the prediction and
        return 'None' instead as the score.

        median_filter_size applies a median filter to the last size predictions
        which are not none when size is > 0 - useful for smoothing spikes due to
        mis-scores in games where the score changes quickly/often
        """
        if median_filter_size is None: median_filter_size = 0

        model_path = path(model_path)
        self.crop_coords = crop_coords
        self.detection_to_score = detection_to_score
        self.model = self.load_model(model_path)
        self.prob_threshold = prob_threshold
        self.median_filter_size = median_filter_size
        self.max_delta = max_delta
        self._score = CropCache(self._score, self.crop_coords, 'OCRScorerV0')
        self.subscription = [self.crop_coords]
        if max_delta is not None:
            self.prev_score = None

        self.reset()
        self.last_score_debug_info = None  # Debug info about the last call to `score()`

    def load_model(self, model_path):
        # Load dynamically so consumers of this library don't
        # necessarily need tensorflow.
        import tensorflow as tf
        params = [np.load(model_path+'_%s.npy'%str(n).zfill(2)) for n in range(1, 27)]
        vs = [tf.Variable(p) for p in params]

        def lrelu(x, leak=0.2):
            f1 = 0.5 * (1 + leak)
            f2 = 0.5 * (1 - leak)
            return f1 * x + f2 * tf.abs(x)

        def conv_block(X, w, b, w2, b2, w3, b3):
            h = lrelu(tf.nn.conv2d(X, w, strides=[1, 1, 1, 1], padding='SAME', use_cudnn_on_gpu=False)+b)
            h2 = lrelu(tf.nn.conv2d(h, w2, strides=[1, 1, 1, 1], padding='SAME', use_cudnn_on_gpu=False)+b2)
            h3 = lrelu(tf.nn.conv2d(h2, w3, strides=[1, 1, 1, 1], padding='SAME', use_cudnn_on_gpu=False)+b3)
            return h3

        def decoder(h, w, b, w2, b2, w3, b3, w4, b4):
            h = lrelu(tf.nn.conv2d(h, w, strides=[1, 1, 1, 1], padding='VALID', use_cudnn_on_gpu=False)+b)
            h = lrelu(tf.nn.conv2d(h, w2, strides=[1, 1, 1, 1], padding='SAME', use_cudnn_on_gpu=False)+b2)
            h = tf.reduce_mean(h, [1, 2])
            h = lrelu(tf.matmul(h, w3)+b3)
            y = tf.matmul(h, w4)+b4
            y = tf.reshape(tf.concat(1, y), [-1, 11])
            pred = tf.argmax(y, 1)
            prob = tf.reduce_max(tf.nn.softmax(y), 1)
            return pred, prob

        X = tf.placeholder(tf.float32, [1, 16, None, 3])
        h = conv_block(X, *vs[0:1*6])
        p = tf.nn.max_pool(h, [1, 2, 2, 1], [1, 2, 2, 1], padding='VALID')
        h2 = conv_block(p, *vs[1*6:2*6])
        p2 = tf.nn.max_pool(h2, [1, 2, 2, 1], [1, 2, 2, 1], padding='VALID')
        h3 = conv_block(p2, *vs[2*6:3*6])
        y, py = decoder(h3, *vs[3*6:])
        sess = tf.Session()
        sess.run(tf.initialize_all_variables())
        return lambda x:sess.run([y, py], {X:(x/127.5-1.)[np.newaxis, :, :, :]})

    def _record_debug(self, score=None, raw_pred=None, prob=None, info=None):
        """Record debug info about the last call to `score()`"""
        self.last_score_debug_info = {'score': score, 'raw_pred': raw_pred, 'prob': float(prob), 'info': info}

    def _score(self, img):
        """
        Returns: tuple of argmax predicted ocr tokens and probability of the seq
        """
        img = resize(img)
        pred, prob = self.model(img)
        pred = pred.tolist()
        return pred, prob

    def score(self, img):
        """
        Returns: score as a float

        Stores debug info into self.last_score_debug_info
        """
        pred, prob = self._score(img)

        if 10 in pred:
            prob = np.mean(prob[:pred.index(10)+1])
            pred = pred[:pred.index(10)]
        else:
            self._record_debug(info='ocr found no end of sequence - something is wrong')
            return None

        if prob < self.prob_threshold:
            self._record_debug(raw_pred=self.detection_to_score(pred), prob=prob, info='Not confident enough')
            return None

        raw_pred = self.detection_to_score(pred)
        if self.max_delta is not None:
            if raw_pred is not None and self.prev_score is not None:
                delta = abs(self.prev_score - raw_pred)
                if delta > self.max_delta:
                    self._record_debug(raw_pred=raw_pred, prob=prob, info='exceeded max delta - ocr issues or mis-specified threshold')
                    return None
                else:
                    self.prev_score = deepcopy(raw_pred)
            else:
                self.prev_score = deepcopy(raw_pred)

        if self.median_filter_size > 0:
            if raw_pred is not None:
                self.score_history.append(raw_pred)
            if len(self.score_history) == self.median_filter_size:
                pred = np.median(self.score_history)
            else:
                pred = raw_pred
        else:
            pred = raw_pred

        self._record_debug(score=pred, raw_pred=raw_pred, prob=prob)
        return pred

    def reset(self):
        ''' Reset internal state between episodes '''
        self._score.reset()
        if self.max_delta is not None:
            self.prev_score = None
        if self.median_filter_size > 0:
            self.score_history = deque(maxlen=self.median_filter_size)


class MatchImage(object):
    def __init__(self, template_path, crop_coords=None, match_threshold=None, warn_threshold=None):
        """
        MatchImage is used to check a matching crop region of an image.
        (e.g. game over screen)

        Note: the layout of the coordinates to crop are in the following order
                crop_coords=[x, width, y, height]
        """
        template_path = path(template_path)
        template = utils.imread(template_path)
        self.template = crop(template, crop_coords)
        self.template_histogram = self._histogram(self.template)
        self.crop_coords = crop_coords

        # TODO: design is a bit wonky right now since the actual
        # thresholding is done outside of this class. Done that way
        # because the rewarder has some state information useful for
        # deciding whether to log.
        if match_threshold is None:
            match_threshold = 0.002
        if warn_threshold is None:
            warn_threshold = min(match_threshold * 3, match_threshold + 0.1)

        self.match_threshold = match_threshold
        self.warn_threshold = warn_threshold

        self.distance = CropCache(self.distance, self.crop_coords, 'MatchImage')

    def reset(self):
        self.distance.reset()

    def _histogram(self, image):
        import cv2
        return cv2.calcHist([image], [1], None, [256], [0, 256])

    def distance(self, other):
        histogram = self._histogram(other)
        normalized_distance = np.sqrt(((self.template_histogram - histogram)**2).sum() / (self.template_histogram**2).sum())
        return normalized_distance
