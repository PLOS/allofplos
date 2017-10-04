from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='allofplos',
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.8.0',
    description='Get and analyze all PLOS articles',
    long_description=long_description,
    url='https://github.com/PLOS/allofplos',
    author='Elizabeth Seiver',
    author_email='eseiver@plos.org',
    license='MIT',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='science PLOS publishing',
    #packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    packages=['allofplos'],
    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['certifi==2017.7.27.1', 'chardet>=3.0.4', 'idna>=2.6',
                      'lxml>=4.0.0', 'progressbar2>=3.34.3', 'python-utils>=2.2.0',
                      'requests>=2.18.4', 'six>=1.11.0', 'tqdm==4.17.1',
                      'urllib3==1.22']
    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    ##package_data={
    ##    'sample': ['package_data.dat'],
    ##},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    ##data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    ##entry_points={
    ##    'console_scripts': [
    ##        'sample=sample:main',
    ##    ],
    ##},
)
