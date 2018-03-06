from setuptools import setup, find_packages
from os import path
import sys

if sys.version_info.major < 3:
    sys.exit('Sorry, Python < 3.4 is not supported')
elif sys.version_info.minor < 4:
    sys.exit('Sorry, Python < 3.4 is not supported')

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


extras_require = {
    'test': ['pytest>=3.4.2'], 
}
extras_require['all'] = sum(extras_require.values(), [])

setup(
    name='allofplos',
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.11.0',
    description='Get and analyze all PLOS articles',
    long_description=long_description,
    url='https://github.com/PLOS/allofplos',
    author='Elizabeth Seiver, Sebastian Bassi, M Pacer',
    author_email='eseiver@plos.org, sebastian.bassi@globant.com, mpacer@berkeley.edu',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='science PLOS publishing',
    packages=find_packages(),
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'certifi>=2017.7.27.1',
        'chardet>=3.0.4',
        'idna>=2.6',
        'lxml>=4.0.0',
        'peewee>=2.10.2',
        'python-utils>=2.2.0',
        'requests>=2.18.4',
        'six>=1.11.0',
        'tqdm>=4.17.1',
        'urllib3>=1.22',
        'unidecode>=0.04.21',
        ],
    extras_require = extras_require,
    python_requires='>=3.4',
    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        'allofplos': ['starter.db'],
        'allofplos.starter_corpus': ['*.xml'],
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    ##data_files=[('my_data', ['data/data_file'])],

    entry_points={
        'console_scripts': [
            'plos_corpus=allofplos.corpus.plos_corpus:main',
        ],
    },
)
