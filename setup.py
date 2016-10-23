#!/usr/bin/env python
# -*- coding: utf-8 -*-
''' distribute- and pip-enabled setup.py '''
from __future__ import print_function
import os
import re
import sys
import glob
import logging
import shutil

logger = logging.getLogger(__name__)
# ----- overrides -----

# set these to anything but None to override the automatic defaults
packages = None
package_name = None
package_data = None
# ---------------------


# ----- control flags -----

# fallback to setuptools if distribute isn't found
setup_tools_fallback = True

# don't include subdir named 'tests' in package_data
skip_tests = False

# print some extra debugging info
debug = True

# -------------------------

if debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

# distribute import and testing
try:
    import distribute_setup
    distribute_setup.use_setuptools()
    logger.info("distribute_setup.py imported and used")
except ImportError:
    # falback to setuptools?
    # distribute_setup.py was not in this directory
    if not (setup_tools_fallback):
        import setuptools
        if not (hasattr(setuptools, '_distribute')
                and setuptools._distribute):
            raise ImportError("distribute was not found and fallback to "
                              "setuptools was not allowed")
        else:
            logger.debug("distribute_setup.py not found, defaulted to "
                          "system distribute")
    else:
        logger.debug("distribute_setup.py not found, defaulting to system "
                      "setuptools")


import setuptools

def find_scripts():
    bin_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'src', 'bin'
    )
    scripts = list()
    for f in os.listdir(bin_path):
        if not f.endswith('pyc'):
            script_path = os.path.relpath(
                os.path.join(bin_path, f),
                os.path.abspath(os.path.dirname(__file__))
            )
            scripts.append(script_path)
    return scripts


def get_version():
    src_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'src', 'lib', 'tmsetup'
    )
    sys.path = [src_path] + sys.path
    import version
    return version.__version__


setuptools.setup(
    name='tmsetup',
    version=get_version(),
    description='Interface for setting up TissueMAPS in the cloud.',
    author='Markus D. Herrmann',
    author_email='markusdherrmann@gmail.com',
    url='https://github.com/tissuemaps/tmclient',
    platforms=['Linux', 'OS-X'],
    classifiers=[
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: System :: Emulators',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python',
        'Development Status :: 4 - Beta',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS'
    ],
    scripts=find_scripts(),
    packages=setuptools.find_packages(os.path.join('src', 'lib')),
    package_dir={'tmsetup': os.path.join('src', 'lib')},
    package_data={'': ['*.rst']},
    include_package_data=True,
    install_requires=[
       'PyYAML>=3.11'
    ]
)

