""" Includes all global variables
"""

import os

from allofplos.plos_regex import validate_filename, validate_doi, corpusdir

# URL bases for PLOS's Solr instances, that index PLOS articles
BASE_URL_API = 'http://api.plos.org/search'

# URL bases for PLOS's raw article XML
EXT_URL_TMP = 'http://journals.plos.org/plosone/article/file?id={0}&type=manuscript'
INT_URL_TMP = 'http://contentrepo.plos.org:8002/v1/objects/mogilefs-prod-repo?key={0}.XML'
URL_TMP = EXT_URL_TMP

BASE_URL_DOI = 'https://doi.org/'
url_suffix = '&type=manuscript'
INT_URL_SUFFIX = '.XML'
prefix = '10.1371/'
suffix_lower = '.xml'
annotation = 'annotation'
correction = 'correction'
annotation_url = 'http://journals.plos.org/plosone/article/file?id=10.1371/annotation/'
annotation_url_int = 'http://contentrepo.plos.org:8002/v1/objects/mogilefs-prod-repo?key=10.1371/annotation/'
annotation_doi = '10.1371/annotation'
BASE_URL_ARTICLE_LANDING_PAGE = 'http://journals.plos.org/plosone/article?id='


def filename_to_url(filename, plos_network=False):
    """
    For a local XML file in the corpusdir directory, transform it to the downloadable URL where its XML resides
    Includes transform for the 'annotation' DOIs
    Example:
    filename_to_url('allofplos_xml/journal.pone.1000001.xml') = \
    'http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001'
    :param file: relative path to local XML file in the corpusdir directory
    :param directory: defaults to corpusdir, containing article files
    :return: online location of a PLOS article's XML
    """
    if correction in filename:
        article = 'annotation/' + (filename.split('.', 4)[2])
    else:
        article = os.path.splitext((os.path.basename(filename)))[0]
    doi = prefix + article
    return doi_to_url(doi, plos_network)


def filename_to_doi(filename):
    """
    For a local XML file in the corpusdir directory, transform it to the article's DOI
    Includes transform for the 'annotation' DOIs
    Uses regex to make sure it's a file and not a DOI
    Example:
    filename_to_doi('journal.pone.1000001.xml') = '10.1371/journal.pone.1000001'
    :param article_file: relative path to local XML file in the corpusdir directory
    :param directory: defaults to corpusdir, containing article files
    :return: full unique identifier for a PLOS article
    """
    if correction in filename and validate_filename(filename):
        article = 'annotation/' + (filename.split('.', 4)[2])
        doi = prefix + article
    elif validate_filename(filename):
        doi = prefix + os.path.splitext((os.path.basename(filename)))[0]
    # NOTE: A filename should never validate as a DOI, so the next elif is wrong.
    elif validate_doi(filename):
        doi = filename
    return doi


def url_to_path(url, directory=corpusdir, plos_network=False):
    """
    For a given PLOS URL to an XML file, return the relative path to the local XML file
    Example:
    url_to_path('http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001') = \
    'allofplos_xml/journal.pone.1000001.xml'
    :param url: online location of a PLOS article's XML
    :param directory: defaults to corpusdir, containing article files
    :return: relative path to local XML file in the corpusdir directory
    """
    annot_prefix = 'plos.correction.'
    if url.startswith(annotation_url) or url.startswith(annotation_url_int):
        # NOTE: REDO THIS!
        file_ = os.path.join(directory,
                             annot_prefix +
                             url[url.index(annotation_doi + '/')+len(annotation_doi + '/'):].
                             replace(url_suffix, '').
                             replace(INT_URL_SUFFIX, '') + '.xml')
    else:
        file_ = os.path.join(directory,
                             url[url.index(prefix)+len(prefix):].
                             replace(url_suffix, '').
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
    return url[url.index(prefix):].rstrip(url_suffix).rstrip(INT_URL_SUFFIX)


def doi_to_url(doi, plos_network=False):
    """
    For a given PLOS DOI, return the PLOS URL to that article's XML file
    Example:
    doi_to_url('10.1371/journal.pone.1000001') = \
    'http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.1000001'
    :param doi: full unique identifier for a PLOS article
    :return: online location of a PLOS article's XML
    """
    URL_TMP = INT_URL_TMP if plos_network else EXT_URL_TMP
    return URL_TMP.format(doi)


def doi_to_path(doi, directory=corpusdir):
    """
    For a given PLOS DOI, return the relative path to that local article
    For DOIs that contain the word 'annotation', searches online version of the article xml to extract
    the journal name, which goes into the filename. Will print DOI if it can't find the journal name
    Uses regex to make sure it's a DOI and not a file
    Example:
    doi_to_path('10.1371/journal.pone.1000001') = 'allofplos_xml/journal.pone.1000001.xml'
    :param doi: full unique identifier for a PLOS article
    :param directory: defaults to corpusdir, containing article files
    :return: relative path to local XML file
    """
    if doi.startswith(annotation_doi) and validate_doi(doi):
        article_file = os.path.join(directory, "plos.correction." + doi.split('/')[-1] + suffix_lower)
    elif validate_doi(doi):
        article_file = os.path.join(directory, doi.lstrip(prefix) + suffix_lower)
    # NOTE: The following check is weird, a DOI should never validate as a file name.
    elif validate_filename(doi):
        article_file = doi
    return article_file
