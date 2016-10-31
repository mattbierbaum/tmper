#from setuptools import setup
import re
from distutils.core import setup

# exctract version from the main python file
version = re.findall(r".*__version__ = \'(.*)\'.*", open('./tmpr').read())[0]

setup(name='tmpr',
      license='MIT License',
      author='Matt Bierbaum',
      version=version,

      install_requires=["tornado>=4.3"],
      scripts=['tmpr']
)
