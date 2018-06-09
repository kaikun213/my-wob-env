from setuptools import setup
import sys, os.path

setup(name='gym_wob',
      version='0.0.1',
      install_requires=[
          'dill',
          'gym',
          'ipdb',
          'faketime',
          'jinja2',
          'manhole',
          'numpy',
          'redis',
          'selenium',
          'ujson',
      ]
)
