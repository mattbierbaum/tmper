#from setuptools import setup
import os
import re
from distutils.core import setup

def read(filename):
    return open(os.path.join(os.path.dirname(__file__), filename)).read()

def version():
    return re.findall(r".*__version__ = \'(.*)\'.*", read('tmpr'))[0]

def readme():
    return read('README.md')

setup(name='tmpr',
      license='MIT License',
      author='Matt Bierbaum',
      version=version(),

      install_requires=["tornado>=4.3"],
      scripts=['tmpr'],

      summary='Temporary file sharing using simple two digit codes.',
      long_description=readme(),
)
