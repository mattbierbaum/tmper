#from setuptools import setup
import os
import re
from distutils.core import setup

def read(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()

try:
    readme = read('README.md')
except IOError as e:
    readme = ''

setup(name='tmpr',
      license='MIT License',
      author='Matt Bierbaum',
      url='https://github.com/mattbierbaum/tmpr',
      version='0.4.3',

      install_requires=["tornado>=4.3"],
      scripts=['tmpr'],
      package_data={'': ['README.md']},

      platforms='osx, posix, linux, windows',
      description='Temporary file sharing using simple two digit codes.',
      long_description=readme,
)
