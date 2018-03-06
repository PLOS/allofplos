""" Includes all global variables
"""
from collections import OrderedDict
import os

from . import get_corpus_dir

from .plos_regex import validate_filename, validate_doi
from .elements import Journal

# URL bases for PLOS's Solr instances, that index PLOS articles
BASE_URL_API = 'http://api.plos.org/search'

BASE_URL_DOI = 'https://doi.org/'
URL_SUFFIX = '&type=manuscript'
INT_URL_SUFFIX = '.XML'
PREFIX = '10.1371/'
SUFFIX_LOWER = '.xml'
annotation = 'annotation'
correction = 'correction'
ANNOTATION_URL = 'http://journals.plos.org/plosone/article/file?id=10.1371/annotation/'
ANNOTATION_DOI = '10.1371/annotation'
BASE_URL_ARTICLE_LANDING_PAGE = 'http://journals.plos.org/plos{}/article?id={}'
BASE_URL_LANDING_PAGE = 'http://journals.plos.org/plos{}/'
LANDING_PAGE_SUFFIX = '{}?id={}'
doi_url = 'https://doi.org/'

plos_page_dict = {'article': 'article',
                  'asset': 'article/asset',
                  'articleFigsAndTables': 'article/assets/figsAndTables',
                  'articleAuthors': 'article/authors',
                  'citationDownloadPage': 'article/citation',
                  'downloadBibtexCitation': 'article/citation/bibtex',
                  'downloadRisCitation': 'article/citation/ris',
                  'figuresPage': 'article/figures',
                  'assetFile': 'article/file',
                  'assetXMLFile': 'article/file',
                  'articleMetrics': 'article/metrics',
                  'articleRelated': 'article/related'}


def _get_base_page(journal):
    """Make the base of a PLOS URL journal-specific.

    Defaults to PLOS ONE.

    Use in conjunction with `get_page()` in the Article class.
    """
    journal_map = {'PLOS ONE': 'one',
                   'PLOS Computational Biology': 'compbiol',
                   'PLOS Neglected Tropical Diseases': 'ntds',
                   'PLOS Genetics': 'genetics',
                   'PLOS Pathogens': 'pathogens',
                   'PLOS Biology': 'biology',
                   'PLOS Medicine': 'medicine',
                   'PLOS Clinical Trials': 'ctr',
                   }
    try:
        url = BASE_URL_LANDING_PAGE.format(journal_map[journal])
    except KeyError:
        print('URL error for {}'.format(journal))
        url = BASE_URL_LANDING_PAGE.format('one')

    return url


def filename_to_url(filename):
    """
    Transform filename into a downloadable URL where its XML resides
    Includes transform for the 'annotation' DOIs
    Example:
    filename_to_url('allofplos_xml/journal.pone.1000001.xml') = \
    'http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001'

    :param filename: string representing a filename
    :return: online location of a PLOS article's XML
    """
    if correction in filename:
        article = 'annotation/' + (filename.split('.', 4)[2])
    else:
        article = os.path.splitext((os.path.basename(filename)))[0]
    doi = PREFIX + article
    return doi_to_url(doi)


def filename_to_doi(filename):
    """
    Transform filename into the article's DOI.
    Includes transform for the 'annotation' DOIs.
    Uses regex to make sure it's a file and not a DOI
    Example:
    filename_to_doi('journal.pone.1000001.xml') = '10.1371/journal.pone.1000001'

    :param filename: relative path to local XML file in the get_corpus_dir() directory
    :return: full unique identifier for a PLOS article
    """
    filename = os.path.basename(filename)
    if not validate_filename(filename):
        raise Exception("Invalid format for PLOS filename: {}".format(filename))
    elif correction in filename:
        article = 'annotation/' + filename.split('.', 4)[2]
        doi = PREFIX + article
    else:
        doi = PREFIX + os.path.splitext(filename)[0]
    return doi


def url_to_path(url, directory=None):
    """
    For a given PLOS URL to an XML file, return the relative path to the local XML file
    Example:
    url_to_path('http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001') = \
    'allofplos_xml/journal.pone.1000001.xml'
    :param url: online location of a PLOS article's XML
    :param directory: defaults to get_corpus_dir(), containing article files
    :return: relative path to local XML file in the directory
    """
    if directory is None:
        directory = get_corpus_dir()
    annot_prefix = 'plos.correction.'
    if url.startswith(ANNOTATION_URL):
        # NOTE: REDO THIS!
        file_ = os.path.join(directory,
                             annot_prefix +
                             url[url.index(ANNOTATION_DOI + '/')+len(ANNOTATION_DOI + '/'):].
                             replace(URL_SUFFIX, '').
                             replace(INT_URL_SUFFIX, '') + '.xml')
    else:
        file_ = os.path.join(directory,
                             url[url.index(PREFIX)+len(PREFIX):].
                             replace(URL_SUFFIX, '').
                             replace(INT_URL_SUFFIX, '') + '.xml')
    return file_


def url_to_doi(url):
    """
    For a given PLOS URL to an XML file, transform it to the article's DOI
    Example:
    url_to_path('http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001') = \
    '10.1371/journal.pone.1000001'
    :param url: online location of a PLOS article's XML
    :return: full unique identifier for a PLOS article
    """
    return url[url.index(PREFIX):].rstrip(URL_SUFFIX).rstrip(INT_URL_SUFFIX)


def doi_to_url(doi):
    """
    For a given PLOS DOI, return the PLOS URL to that article's XML file
    Example:
    doi_to_url('10.1371/journal.pone.1000001') = \
    'http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001'
    :param doi: full unique identifier for a PLOS article
    :return: online location of a PLOS article's XML
    """
    if validate_doi(doi) is False:
        raise Exception("Invalid format for PLOS DOI: {}".format(doi))
    journal = Journal.doi_to_journal(doi)
    base_page = _get_base_page(journal)
    return ''.join([base_page, 'article/file?id=', doi, URL_SUFFIX])


def doi_to_path(doi, directory=None):
    """
    For a given PLOS DOI, return the relative path to that local article
    For DOIs that contain the word 'annotation', searches online version of the article xml to extract
    the journal name, which goes into the filename. Will print DOI if it can't find the journal name
    Uses regex to make sure it's a DOI and not a file
    Example:
    doi_to_path('10.1371/journal.pone.1000001') = 'allofplos_xml/journal.pone.1000001.xml'
    :param doi: full unique identifier for a PLOS article
    :param directory: defaults to get_corpus_dir(), containing article files
    :return: relative path to local XML file
    """
    if directory is None:
        directory = get_corpus_dir()
    if not validate_doi(doi):
        raise Exception("Invalid format for PLOS DOI: {}".format(doi))
    elif doi.startswith(ANNOTATION_DOI):
        article_file = os.path.join(directory, "plos.correction." + doi.split('/')[-1] + SUFFIX_LOWER)
    else:
        article_file = os.path.join(directory, doi.lstrip(PREFIX) + SUFFIX_LOWER)
    return article_file


def convert_country(country):
    """
    For a given country, transform it using one of these rules
    :param country: string with the country name
    :return: string with the normalized country name
    """
    if (country and 'China' in country) or \
            country == 'Chin' or country == 'CHINA':
        country = 'China'
    elif country and 'Brazil' in country or \
            country == 'Brasil' or \
            country == 'ITA - Instituto Tecnologico de Aeronautica (':
        country = 'Brazil'
    elif country and 'Argentina' in country:
        country = 'Argentina'
    elif country == 'Czechia':
        country = 'Czech Republic'
    elif 'Norwegian' in country:
        country = 'Norway'
    elif country and 'United Kingdom' in country:
        country = 'United Kingdom'
    elif country and 'Hong Kong' in country:
        country = 'Hong Kong'
    elif country == 'Cameroun':
        country = 'Cameroon'
    elif (country and 'Chile' in country) or country == 'CHILE':
        country = 'Chile'
    elif (country and 'United States of America' in \
            country) or country == 'United States' or country \
            == 'USA' or 'Florida' in country or \
            'California' in country or\
            country == 'National Reference Centre for' or \
            country == 'United State of America' or \
            country == 'U.S.A.' or \
            country == 'Virginia':
        country = 'United States of America'
    elif country=='Republic of Panamá' or country=='Panamá' or 'Panama' in country:
        country = 'Panama'
    elif 'Canada' in country:
        country = 'Canada'
    elif 'Colombia' in country or country == 'Universidad Aut':
        country = 'Colombia'
    elif 'Spain' in country or country=='España':
        country = 'Spain'
    elif 'Iran' in country:
        country = 'Iran'
    elif 'Saudi Arabia' in country:
        country = 'Saudi Arabia'
    elif 'Italy' in country:
        country = 'Italy'
    elif 'Japan' in country:
        country = 'Japan'
    elif 'Germany' in country:
        country = 'Germany'
    elif 'Luxembourg' in country:
        country = 'Luxembourg'
    elif ('France' in country) or country == 'Marseille':
        country = 'France'
    elif country == 'ROC' or country == 'R. O. C':
        country = 'Taiwan'
    elif country == 'Brasil':
        country = 'Brazil'
    elif country == 'México' or 'Mexico' in country or \
            country == 'Centro de Investigación':
        country = 'Mexico'
    elif 'Slowakia' in country:
        country = 'Slowakia'
    elif country == 'Korea' or 'Republic of Korea' in country:
        country = 'South Korea'
    elif country == 'United Kindgom':
        country = 'United Kingdom'
    elif country and 'Netherlands' in country:
        country = 'Netherlands'
    elif country == 'Commonwealth of Australia' or 'Australia' in country:
        country = 'Australia'
    elif 'Singapore' in country:
        country = 'Singapore'
    elif country and (country[0].isdigit() or country[0] == '+'):
        country = 'N/A'
    return country
