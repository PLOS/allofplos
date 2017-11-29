#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script is for downloading and maintaining a local copy of all of the XML files of PLOS articles.
By default it doesn't rely on access to the PLOS's internal network (but can use it if available).
Diagram of relevant systems here: https://confluence.plos.org/confluence/display/CXP/How+allofPLOS+works
Workflow:
Check whether list of DOI files is complete
    * query Solr API for list of new articles (limited by date)
    * create list of missing DOIs, by comparing against existing list of DOIs or file names
Update by downloading articles content-repo if local store is not complete
Check for and download corrected articles that have been issued corrections
Check for and download versions of record (VOR) for uncorrected proofs
Zip folder down, appending when able
Create log file for actions that can be referenced

TODO: add start date for beginning of time for article pubdates (2003-08-11), calculation for most recent pub date
"""

import argparse
import datetime
import errno
import gzip
import logging
import os
import shutil
import time
import tarfile
import zipfile

import lxml.etree as et
import progressbar
import requests
from tqdm import tqdm

from allofplos.plos_regex import (validate_doi, corpusdir, newarticledir)
from allofplos.transformations import (BASE_URL_API, EXT_URL_TMP, INT_URL_TMP, URL_TMP, filename_to_doi,
                                       doi_to_path)

help_str = "This program downloads a zip file with all PLOS articles and checks for updates"

# Making sure DS.Store not included as file
ignore_func = shutil.ignore_patterns('.DS_Store')

# List of uncorrected proof articles to check for updates
uncorrected_proofs_text_list = 'uncorrected_proofs_list.txt'

# Some example URLs that may be useful
EXAMPLE_VOR_URL = ('http://solr-101.soma.plos.org:8011/solr/collection1/select?'
                   'q=id%3A+10.1371%2Fjournal.pgen.1006621%0A&fq=publication_stage%3A+vor-update-to-uncorrected-proof'
                   '&fl=publication_stage%2C+id&wt=json&indent=true')
EXAMPLE_SEARCH_URL = ('http://api.plos.org/search?q=*%3A*&fq=doc_type%3Afull&fl=id,'
                      '&wt=json&indent=true&fq=article_type:"research+article"+OR+article_type:"correction"+OR+'
                      'article_type:"meta-research+article"&sort=%20id%20asc&'
                      'fq=publication_date:%5B2017-03-05T00:00:00Z+TO+2017-03-19T23:59:59Z%5D&start=0&rows=1000')

# Starting out list of needed articles as empty
dois_needed_list = []

# For zip file and google drive
zip_id = '0B_JDnoghFeEKLTlJT09IckMwOFk'
metadata_id = '0B_JDnoghFeEKQUhKWXBOVy1aTlU'
local_zip = 'allofplos_xml.zip'
zip_metadata = 'zip_info.txt'
time_formatting = "%Y_%b_%d_%Hh%Mm%Ss"
min_files_for_valid_corpus = 200000
test_zip_id = '12VomS72LdTI3aYn4cphYAShv13turbX3'
local_test_zip = 'sample_corpus.zip'


def listdir_nohidden(path, extension='.xml', include_dir=True):
    """
    Make a list of all files of a given extension in a given directory
    Option to include local path in filename
    :param path: String with a path where to search files
    :param extension: String with the extension that we are looking for, xml is the default value
    :param include_dir: By default, include the directory in the filename
    :return: A list with all the file names inside this directory, without the DS_Store file
    """

    if include_dir:
        file_list = [os.path.join(path, file) for file in os.listdir(path)
                     if file.endswith(extension) and 'DS_Store' not in file]
    else:
        file_list = [file for file in os.listdir(path) if file.endswith(extension) and
                     'DS_Store' not in file]
    return file_list


def extract_filenames(directory, extension='.xml'):
    """
    Make a list of all files of a given extension in a given directory, without their extension
    :param directory: String with the directory where to search files
    :param extension: String with the extension that we are looking for, xml is the default value
    :return: A list with all the file names inside this directory, excluding extensions
    """
    filenames = [os.path.basename(article_file).rstrip(extension) for article_file in
                 listdir_nohidden(directory, extension) if os.path.isfile(article_file)]
    return filenames


def search_solr_records(days_ago=14, start=0, rows=1000, start_date=None, end_date=None, item='id'):
    """
    Queries the solr database for a list of articles based on the date of publication
    function defaults to querying by DOI (i.e., 'id')
    TODO (on hold): if Solr XSLT is changed, query by revision_date instead of publication_date.
    Then would be used in separate query to figure out updated articles to download
    for full list of potential queries, see http://api.plos.org/solr/search-fields/
    :param days_ago: A int value with the length of the queried date range, default is two weeks
    :param start: An int value indicating the first row of results to return
    :param rows: An int value indicating how many rows of results to return (from 0)
    :param start_date: datetime object of earliest date in the queried range (defaults to None)
    :param end_date: datetime object of latest date in the queried range (defaults to now)
    :param item: Items to return/display. 'Id', the default, is the article DOI.
    :return: A list of DOIs for articles published in this time period; by default, from the last two weeks
    """
    if end_date is None:
        end_date = datetime.datetime.now()
    solr_search_results = []
    if start_date is None:
        earlier = datetime.timedelta(days=days_ago)
        start_date = end_date - earlier
    START_DATE = start_date.strftime("%Y-%m-%d")
    END_DATE = end_date.strftime("%Y-%m-%d")
    howmanyarticles_url_base = [BASE_URL_API,
                                '?q=*:*&fq=doc_type:full+-doi:image&fl=id,',
                                item,
                                '&wt=json&indent=true&sort=%20id%20asc&fq=publication_date:[',
                                START_DATE,
                                'T00:00:00Z+TO+',
                                END_DATE,
                                'T23:59:59Z]'
                                ]
    howmanyarticles_url = ''.join(howmanyarticles_url_base) + '&rows=1000'
    # if include_uncorrected is False:
    num_results = requests.get(howmanyarticles_url).json()["response"]["numFound"]

    # Create solr_search_results & paginate through results
    while(start < num_results):
        query_url = ''.join(howmanyarticles_url_base) + '&start=' + str(start) + '&rows=' + str(rows)
        article_search = requests.get(query_url).json()
        solr_search_results = [x[item] for x in article_search["response"]["docs"]]
        start = start + rows
        if start + rows > num_results:
            rows = num_results - start
    print("URL for solr query:", howmanyarticles_url)

    if solr_search_results:
        print("{0} results returned from this search."
              .format(len(solr_search_results)))
    else:
        print('No results returned for this search.')
    return solr_search_results


def get_all_solr_dois():
    """
    Get every article published by PLOS, up to 500,000, as indexed by Solr on api.plos.org.
    URL includes regex to exclude sub-DOIs and image DOIs.
    :return: list of DOIs for all PLOS articles
    """
    solr_magic_url = ('http://api.plos.org/terms?terms.fl=id&terms.limit=500000&wt=json&indent=true&terms.regex='
                      '10%5C.1371%5C/(journal%5C.p%5Ba-zA-Z%5D%7B3%7D%5C.%5B%5Cd%5D%7B7%7D$%7Cannotation%5C/'
                      '%5Ba-zA-Z0-9%5D%7B8%7D-%5Ba-zA-Z0-9%5D%7B4%7D-%5Ba-zA-Z0-9%5D%7B4%7D-%5Ba-zA-Z0-9%5D'
                      '%7B4%7D-%5Ba-zA-Z0-9%5D%7B12%7D$)')
    results = requests.get(solr_magic_url).json()
    solr_dois = [id for id in results['terms']['id'] if isinstance(id, str)]

    return solr_dois


def get_dois_needed_list(comparison_list=None, directory=corpusdir):
    """
    Takes result of query from get_all_solr_dois and compares to local article directory.
    :param comparison_list: Defaults to creating a full list of local article files.
    :param directory: An int value indicating the first row of results to return
    :return: A list of DOIs for articles that are not in the local article directory.
    """
    if comparison_list is None:
        comparison_list = get_all_solr_dois()

    # Transform local files to DOIs
    local_article_list = [filename_to_doi(article) for article in listdir_nohidden(directory, '.xml')]

    dois_needed_list = list(set(comparison_list) - set(local_article_list))
    if dois_needed_list:
        print(len(dois_needed_list), "new articles to download.")
    else:
        print("No new articles found to add to Corpus folder.")
    return dois_needed_list


def copytree(source, destination, symlinks=False, ignore=None):
    """
    Copies all the files in one directory to another
    :param source: Original directory of files
    :param destination: Directory where files are copied to
    :param symlinks: param from the shutil.copytree function
    :param ignore: param from the shutil.copytree function; default is include all files
    :return: None
    """
    for item in listdir_nohidden(source, include_dir=False):
        s = os.path.join(source, item)
        d = os.path.join(destination, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


def repo_download(dois, tempdir, ignore_existing=True, plos_network=False):
    """
    Downloads a list of articles by DOI from PLOS's content-repo (crepo) to a temporary directory
    Use in conjunction with get_dois_needed_list
    :param dois: Iterable with DOIs for articles to obtain
    :param tempdir: Temporary directory where files are copied to
    :param ignore_existing: Don't re-download to tempdir if already downloaded
    """
    # make temporary directory, if needed
    try:
        os.mkdir(tempdir)
    except FileExistsError:
        pass

    if ignore_existing:
        existing_articles = [filename_to_doi(file) for file in listdir_nohidden(tempdir)]
        dois = set(dois) - set(existing_articles)

    max_value = len(dois)
    bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
    for i, doi in enumerate(sorted(dois)):
        url = URL_TMP.format(doi)
        articleXML = et.parse(url)
        article_path = doi_to_path(doi, directory=tempdir)
        # create new local XML files
        if ignore_existing is False or ignore_existing and os.path.isfile(article_path) is False:
            with open(article_path, 'w') as file:
                file.write(et.tostring(articleXML, method='xml', encoding='unicode'))
            if not plos_network:
                time.sleep(1)
        bar.update(i+1)
    bar.finish()
    print(len(listdir_nohidden(tempdir)), "new articles downloaded.")
    logging.info(len(listdir_nohidden(tempdir)))


def move_articles(source, destination):
    """
    Move articles from one folder to another
    :param source: Temporary directory of new article files
    :param destination: Directory where files are copied to
    :return: None
    """
    oldnum_destination = len(listdir_nohidden(destination))
    oldnum_source = len(listdir_nohidden(source))
    if oldnum_source > 0:
        print('Corpus started with {0} articles.\n'
              'Moving new and updated files...'.format(oldnum_destination))
        copytree(source, destination, ignore=ignore_func)
        newnum_destination = len(listdir_nohidden(destination))
        print('{0} files moved. Corpus now has {1} articles.'
              .format(oldnum_source, newnum_destination))
        logging.info("New article files moved successfully")
    else:
        print("No files moved.")
        logging.info("No article files moved")
    # Delete temporary folder in most cases
    if source == newarticledir:
        shutil.rmtree(source)


def get_article_xml(article_file, tag_path_elements=None):
    """
    For a local article file, read its XML tree
    Can also interpret DOIs
    Defaults to reading the tree location for uncorrected proofs/versions of record
    :param article_file: the xml file for a single article
    :param tag_path_elements: xpath location in the XML tree of the article file
    :return: content of article file at that xpath location
    """
    if tag_path_elements is None:
        tag_path_elements = ('/',
                             'article',
                             'front',
                             'article-meta',
                             'custom-meta-group',
                             'custom-meta',
                             'meta-value')

    try:
        article_tree = et.parse(article_file)
    except OSError:
        if validate_doi(article_file):
            article_file = doi_to_path(article_file)
        elif article_file.endswith('xml'):
            article_file = article_file[:-3] + 'XML'
        elif article_file.endswith('XML'):
            article_file = article_file[:-3] + 'xml'
        elif article_file.endswith('nxml'):
            article_file = article_file[:-3] + 'nxml'
        elif not article_file.endswith('.'):
            article_file = article_file + '.xml'
        else:
            article_file = article_file + 'xml'
        article_tree = et.parse(article_file)
    articleXML = article_tree.getroot()
    tag_location = '/'.join(tag_path_elements)
    return articleXML.xpath(tag_location)


def check_article_type(article_file):
    """
    For an article file, get its JATS article type
    Use primarily to find Correction (and thereby corrected) articles
    :param article_file: the xml file for a single article
    :return: JATS article_type at that xpath location
    """
    article_type = get_article_xml(article_file=article_file,
                                   tag_path_elements=["/",
                                                      "article"])
    return article_type[0].attrib['article-type']


def get_related_article_doi(article_file, corrected=True):
    """
    For an article file, get the DOI of the first related article
    Use primarily to map Correction notification articles to articles that have been corrected
    NOTE: what to do if more than one related article?
    :param article_file: the xml file for a single article
    :param corrected: default true, part of the Corrections workflow, more strict in tag search
    :return: tuple of partial doi string at that xpath location, related_article_type
    """
    r = get_article_xml(article_file=article_file,
                        tag_path_elements=["/",
                                           "article",
                                           "front",
                                           "article-meta",
                                           "related-article"])
    related_article = ''
    if corrected:
        for x in r:
            if x.attrib['related-article-type'] in ('corrected-article', 'companion'):
                related_article_type = x.attrib['related-article-type']
                corrected_doi = x.attrib['{http://www.w3.org/1999/xlink}href']
                related_article = corrected_doi.lstrip('info:doi/')
                break
    else:
        r = r[0].attrib
        related_article_type = r['related-article-type']
        related_article = r['{http://www.w3.org/1999/xlink}href']
        related_article = related_article.lstrip('info:doi/')

    return related_article, related_article_type


def get_article_pubdate(article_file, date_format='%d %m %Y'):
    """
    For an individual article, get its date of publication
    :param article_file: file path/DOI of the article
    :param date_format: string format used to convert to datetime object
    :return: datetime object with the date of publication
    """
    day = ''
    month = ''
    year = ''
    raw_xml = get_article_xml(article_file=article_file,
                              tag_path_elements=["/",
                                                 "article",
                                                 "front",
                                                 "article-meta",
                                                 "pub-date"])
    for x in raw_xml:
        for name, value in x.items():
            if value == 'epub':
                date_fields = x
                for y in date_fields:
                    if y.tag == 'day':
                        day = y.text
                    if y.tag == 'month':
                        month = y.text
                    if y.tag == 'year':
                        year = y.text
    date = (day, month, year)
    string_date = ' '.join(date)
    pubdate = datetime.datetime.strptime(string_date, date_format)
    return pubdate


def compare_article_pubdate(article, days=22):
    """
    Check if an article's publication date was more than 3 weeks ago.
    :param article: doi/file of the article
    :param days: how long ago to compare the publication date (default 22 days)
    :return: boolean for whether the pubdate was older than the days value
    """
    try:
        pubdate = get_article_pubdate(article)
        today = datetime.datetime.now()
        three_wks_ago = datetime.timedelta(days)
        compare_date = today - three_wks_ago
        return pubdate < compare_date
    except OSError:
        article = os.path.join(newarticledir, article.split('/')[1].rstrip('.xml')+'.xml')
        pubdate = get_article_pubdate(article)
        today = datetime.datetime.now()
        three_wks_ago = datetime.timedelta(days)
        compare_date = today - three_wks_ago
        return pubdate < compare_date
    except ValueError:
        print("Pubdate error in {}".format(article))


def download_updated_xml(article_file,
                         tempdir=newarticledir,
                         vor_check=False):
    """
    For an article file, compare local XML to remote XML
    If they're different, download new version of article
    :param article_file: the filename for a single article
    :param tempdir: directory where files are downloaded to
    :param vor_check: whether checking to see if uncorrected proof is updated
    :return: boolean for whether update was available & downloaded
    """
    doi = filename_to_doi(article_file)
    try:
        os.mkdir(tempdir)
    except FileExistsError:
        pass
    url = URL_TMP.format(doi)
    articletree_remote = et.parse(url)
    articleXML_remote = et.tostring(articletree_remote, method='xml', encoding='unicode')
    if not article_file.endswith('.xml'):
        article_file += '.xml'
    try:
        articletree_local = et.parse(os.path.join(corpusdir, os.path.basename(article_file)))
    except OSError:
        article_file_alt = os.path.join(tempdir, os.path.basename(doi_to_path(article_file)))
        articletree_local = et.parse(article_file_alt)
    articleXML_local = et.tostring(articletree_local, method='xml', encoding='unicode')

    if articleXML_remote == articleXML_local:
        updated = False
        get_new = False
    else:
        get_new = True
        if vor_check:
            # make sure that update is to a VOR for uncorrected proof
            get_new = False
            path_parts = ['/',
                          'article',
                          'front',
                          'article-meta',
                          'custom-meta-group',
                          'custom-meta',
                          'meta-value']
            r = articletree_remote.xpath("/".join(path_parts))
            for x in r:
                if x.text == 'vor-update-to-uncorrected-proof':
                    get_new = True
                    break
        if get_new:
            article_path = os.path.join(tempdir, os.path.basename(article_file))
            with open(article_path, 'w') as file:
                file.write(articleXML_remote)
            updated = True
    return updated


def check_for_corrected_articles(directory=newarticledir, article_list=None):
    """
    For articles in the temporary download directory, check if article_type is correction
    If correction, surface the DOI of the article being corrected
    Use with download_corrected_articles
    :param article: the filename for a single article
    :param directory: directory where the article file is, default is newarticledir
    :return: list of filenames to existing local files for articles issued a correction
    """
    corrected_doi_list = []
    if article_list is None:
        article_list = listdir_nohidden(directory)
    for article_file in article_list:
        article_type = check_article_type(article_file=article_file)
        if article_type == 'correction':
            corrected_article = get_related_article_doi(article_file)[0]
            corrected_doi_list.append(corrected_article)
    corrected_article_list = [doi_to_path(doi) if os.path.exists(doi_to_path(doi)) else
                              doi_to_path(doi, directory=newarticledir) for doi in list(corrected_doi_list)]
    print(len(corrected_article_list), 'corrected articles found.')
    return corrected_article_list


def download_corrected_articles(directory=corpusdir, tempdir=newarticledir, corrected_article_list=None):
    """
    For a list of articles that have been corrected, check if the xml was updated
    Many corrections don't result in XML changes

    Use with download_corrected articles
    :param article: the filename for a single article
    :param directory: directory where the article file is, default is newarticledir
    :param tempdir: where new articles are downloaded to-
    :return: list of DOIs for articles downloaded with new XML versions
    """
    if corrected_article_list is None:
        corrected_article_list = check_for_corrected_articles(directory)
    corrected_updated_article_list = []
    print("Downloading corrected articles")
    max_value = len(corrected_article_list)
    bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
    for i, article in enumerate(corrected_article_list):
        updated = download_updated_xml(article)
        if updated:
            corrected_updated_article_list.append(article)
        bar.update(i+1)
    bar.finish()
    print(len(corrected_updated_article_list), 'corrected articles downloaded with new xml.')
    return corrected_updated_article_list


def check_if_uncorrected_proof(article_file):
    """
    For a single article in a directory, check whether it is the 'uncorrected proof' type
    :param article: Partial DOI/filename of the article
    :return: Boolean for whether article is an uncorrected proof (true = yes, false = no)
    """
    tree = get_article_xml(article_file)
    for subtree in tree:
        if subtree.text == 'uncorrected-proof':
            return True
    return False


def get_uncorrected_proofs_list():
    """
    Loads the uncorrected proofs txt file.
    Failing that, creates new txt file from scratch using corpusdir.
    :return: list of DOIs of uncorrected proofs from text list
    """
    try:
        with open(uncorrected_proofs_text_list) as file:
            uncorrected_proofs_list = file.read().splitlines()
    except FileNotFoundError:
        print("Creating new text list of uncorrected proofs from scratch.")
        article_files = listdir_nohidden(corpusdir)
        uncorrected_proofs_list = []
        max_value = len(article_files)
        bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
        for i, article_file in enumerate(article_files):
            bar.update(i+1)
            if check_if_uncorrected_proof(article_file):
                uncorrected_proofs_list.append(filename_to_doi(article_file))
        bar.finish()
        print("Saving uncorrected proofs.")
        with open(uncorrected_proofs_text_list, 'w') as file:
            max_value = len(uncorrected_proofs_list)
            bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
            for i, item in enumerate(sorted(uncorrected_proofs_list)):
                file.write("%s\n" % item)
                bar.update(i+1)
            bar.finish()
    return uncorrected_proofs_list


def check_for_uncorrected_proofs(directory=newarticledir, text_list=uncorrected_proofs_text_list):
    """
    For a list of articles, check whether they are the 'uncorrected proof' type
    One of the checks on newly downloaded articles before they're added to corpusdir
    :param text_list: List of DOIs
    :param directory: Directory containing the article files
    :return: all articles that are uncorrected proofs, including from main article directory
    """

    # Read in uncorrected proofs from uncorrected_proofs_text_list txt file
    # If uncorrected_proofs_list txt file doesn't exist, build that list from scratch from main article directory
    uncorrected_proofs_list = get_uncorrected_proofs_list()

    # Check directory for uncorrected proofs
    # Append uncorrected proofs to running list
    articles = listdir_nohidden(directory)
    new_proofs = 0
    for article_file in articles:
        if check_if_uncorrected_proof(article_file):
            uncorrected_proofs_list.append(filename_to_doi(article_file))
            new_proofs += 1
    # Copy all uncorrected proofs from list to clean text file
    with open(text_list, 'w') as file:
        for item in sorted(set(uncorrected_proofs_list)):
            file.write("%s\n" % item)
    if uncorrected_proofs_list:
        print("{} uncorrected proofs found. {} total in list.".format(new_proofs, len(uncorrected_proofs_list)))
    else:
        print("No uncorrected proofs found in folder or in existing list.")
    return uncorrected_proofs_list


def check_for_vor_updates(uncorrected_list=None):
    """
    For existing uncorrected proofs list,
    check whether a vor is available to download
    :param uncorrected_list: DOIs of uncorrected articles, default None
    :return: List of articles from uncorrected_list for which Solr says there is a new VOR waiting
    """

    # First get/make list of uncorrected proofs
    if uncorrected_list is None:
        uncorrected_list = get_uncorrected_proofs_list()
    # Make it check a single article
    if isinstance(uncorrected_list, str):
        uncorrected_list = [uncorrected_list]

    # Create article list chunks for Solr query no longer than 10 DOIs at a time
    list_chunks = [uncorrected_list[x:x+10] for x in range(0, len(uncorrected_list), 10)]
    vor_updates_available = []
    for chunk in list_chunks:
        article_solr_string = ' OR '.join(chunk)

        # Get up to 10 article records from Solr
        # Filtered for publication_stage = vor-update-to-corrected-proof
        VOR_check_url_base = [BASE_URL_API,
                              '?q=id:(',
                              article_solr_string,
                              ')&fq=publication_stage:vor-update-to-uncorrected-proof&',
                              'fl=publication_stage,+id&wt=json&indent=true']
        VOR_check_url = ''.join(VOR_check_url_base)
        vor_check = requests.get(VOR_check_url).json()['response']['docs']
        vor_chunk_results = [x['id'] for x in vor_check]
        vor_updates_available.extend(vor_chunk_results)

    if vor_updates_available:
        print(len(vor_updates_available), "VOR updates to download.")
        logging.info("VOR updates to download.")
    else:
        print("No new VOR articles indexed in Solr.")
        logging.info("No new VOR articles in Solr")
    return vor_updates_available


def download_vor_updates(directory=corpusdir, tempdir=newarticledir,
                         vor_updates_available=None, plos_network=False):
    """
    For existing uncorrected proofs list, check whether a vor is available to download
    Used in conjunction w/check_for_vor_updates
    Main method doesn't really work because vor updates aren't always indexed properly in Solr,
    so remote_proofs_direct_check is used
    :param directory: Directory containing the article files
    :param tempdir: Directory where updated VORs to be downloaded to
    :param vor_updates_available: Partial DOI/filenames of uncorrected articles, default None
    :return: List of articles from uncorrected_list for which new version successfully downloaded
    """
    if vor_updates_available is None:
        vor_updates_available = check_for_vor_updates()
    vor_updated_article_list = []
    if vor_updates_available:
        for article in vor_updates_available:
            updated = download_updated_xml(article, vor_check=True)
            if updated:
                vor_updated_article_list.append(article)

    old_uncorrected_proofs_list = get_uncorrected_proofs_list()
    new_uncorrected_proofs_list = list(set(old_uncorrected_proofs_list) - set(vor_updated_article_list))

    # direct remote XML check; add their totals to totals above
    if new_uncorrected_proofs_list:
        proofs_download_list = remote_proofs_direct_check(article_list=new_uncorrected_proofs_list,
                                                          plos_network=plos_network)
        vor_updated_article_list.extend(proofs_download_list)
        new_uncorrected_proofs_list = list(set(new_uncorrected_proofs_list) - set(vor_updated_article_list))
        too_old_proofs = [proof for proof in new_uncorrected_proofs_list if compare_article_pubdate(proof)]
        if too_old_proofs and plos_network:
            print("Proofs older than 3 weeks: {}".format(too_old_proofs))

    # if any VOR articles have been downloaded, update static uncorrected proofs list
    if vor_updated_article_list:
        with open(uncorrected_proofs_text_list, 'w') as file:
            for item in sorted(new_uncorrected_proofs_list):
                file.write("%s\n" % item)
        print("{} uncorrected proofs updated to version of record.\n".format(len(vor_updated_article_list)) +
              "{} uncorrected proofs remaining in uncorrected proof list.".format(len(new_uncorrected_proofs_list)))

    else:
        print("No uncorrected proofs have a VOR update.")

    return vor_updated_article_list


def remote_proofs_direct_check(tempdir=newarticledir, article_list=None, plos_network=False):
    """
    Takes list of of DOIs of uncorrected proofs and compared to raw XML of the article online
    If article status is now 'vor-update-to-uncorrected-proof', download new copy
    This will not be necessary once Solr is indexing VOR article information correctly.
    https://developer.plos.org/jira/browse/DPRO-3418
    :param tempdir: temporary directory for downloading articles
    :param article-list: list of uncorrected proofs to check for updates.
    :return: list of all articles with updated vor
    """
    try:
        os.mkdir(tempdir)
    except FileExistsError:
        pass
    proofs_download_list = []
    if article_list is None:
        article_list = get_uncorrected_proofs_list()
    for doi in list(set(article_list)):
        file = doi_to_path(doi)
        updated = download_updated_xml(file, vor_check=True)
        if updated:
            proofs_download_list.append(doi)
    if proofs_download_list:
        print(len(proofs_download_list),
              "VOR articles directly downloaded.")
    else:
        print("No new VOR articles found.")
    return proofs_download_list


def download_check_and_move(article_list, text_list, tempdir, destination,
                            plos_network=False):
    """
    For a list of new articles to get, first download them from content-repo to the temporary directory
    Next, check these articles for uncorrected proofs and article_type corrections
    Act on available VOR updates & corrected articles
    Then, move to corpus directory where the rest of the articles are
    :param article_list: List of new articles to download
    :param text_list: List of uncorrected proofs to check for vor updates
    :param tempdir: Directory where articles to be downloaded to
    :param destination: Directory where new articles are to be moved to
    """
    repo_download(article_list, tempdir, plos_network=plos_network)
    corrected_articles = check_for_corrected_articles(directory=tempdir)
    download_corrected_articles(corrected_article_list=corrected_articles)
    download_vor_updates(plos_network=plos_network)
    check_for_uncorrected_proofs(directory=tempdir)
    move_articles(tempdir, destination)


def download_file_from_google_drive(id, filename, destination=corpusdir,
                                    file_size=None):
    """
    General method for downloading from Google Drive.
    Doesn't require using API or having credentials
    :param id: Google Drive id for file (constant even if filename change)
    :param filename: name of the zip file
    :param destination: directory where to download the zip file, defaults to corpusdir
    :param file_size: size of the file being downloaded
    :return: None
    """
    URL = "https://docs.google.com/uc?export=download"

    file_path = os.path.join(destination, filename)
    if not os.path.isfile(file_path):
        session = requests.Session()

        response = session.get(URL, params={'id': id}, stream=True)
        token = get_confirm_token(response)

        if token:
            params = {'id': id, 'confirm': token}
            response = session.get(URL, params=params, stream=True)
            r = requests.get(URL, params=params, stream=True)
        save_response_content(response, file_path, file_size=file_size)
    return file_path


def get_confirm_token(response):
    """
    Part of keep-alive method for downloading large files from Google Drive
    Discards packets of data that aren't the actual file
    :param response: session-based google query
    :return: either datapacket or discard unneeded data
    """
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None


def save_response_content(response, download_path, file_size=None):
    """
    Saves the downloaded file parts from Google Drive to local file
    Includes progress bar for download %
    :param response: session-based google query
    :param download_path: path to local zip file
    :param file_size: size of the file being downloaded
    :return: None
    """
    CHUNK_SIZE = 32768
    # for downloading zip file
    if os.path.basename(download_path) == local_zip:
        with open(download_path, "wb") as f:
            size = file_size
            pieces = round(size / CHUNK_SIZE)
            with tqdm(total=pieces) as pbar:
                for chunk in response.iter_content(CHUNK_SIZE):
                    pbar.update(1)
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
    # for downloading zip metadata text file
    else:
        with open(download_path, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)


def get_zip_metadata(method='initial'):
    """
    Gets metadata txt file from Google Drive, that has info about zip file
    Used to get the file name, as well as byte size for progress bar
    Includes progress bar for download %
    :param method: boolean if initializing the PLOS Corpus (defaults to True)
    :return: tuple of data about zip file: date zip created, zip size, and location of metadata txt file
    """
    if method == 'initial':
        metadata_path = download_file_from_google_drive(metadata_id, zip_metadata)
    with open(metadata_path) as f:
        zip_stats = f.read().splitlines()
    zip_datestring = zip_stats[0]
    zip_date = datetime.datetime.strptime(zip_datestring, time_formatting)
    zip_size = int(zip_stats[1])
    return zip_date, zip_size, metadata_path


def unzip_articles(file_path,
                   extract_directory=corpusdir,
                   filetype='zip',
                   delete_file=True
                   ):
    """
    Unzips zip file of all of PLOS article XML to specified directory
    :param file_path: path to file to be extracted
    :param extract_directory: directory where articles are copied to
    :param filetype: whether a 'zip' or 'tar' file (tarball), which use different decompression libraries
    :param delete_file: whether to delete the compressed archive after extracting articles
    :return: None
    """
    try:
        os.makedirs(extract_directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    if filetype == 'zip':
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            print("Extracting zip file...")
            zip_ref.extractall(extract_directory)
            print("Extraction complete.")
    elif filetype == 'tar':
        tar = tarfile.open(file_path)
        print("Extracting tar file...")
        tar.extractall(path=extract_directory)
        tar.close()
        print("Extraction complete.")

    if delete_file:
        os.remove(file_path)


def create_local_plos_corpus(corpusdir=corpusdir, rm_metadata=True):
    """
    Downloads a fresh copy of the PLOS corpus by:
    1) creating corpusdir if it doesn't exist
    2) downloading metadata about the .zip of all PLOS XML
    2) downloading the zip file (defaults to corpus directory)
    3) extracting the individual XML files into the corpus directory
    :param corpusdir: directory where the corpus is to be downloaded and extracted
    :param rm_metadata: COMPLETE HERE
    :return: None
    """
    if os.path.isdir(corpusdir) is False:
        os.mkdir(corpusdir)
        print('Creating folder for article xml')
    zip_date, zip_size, metadata_path = get_zip_metadata()
    zip_path = download_file_from_google_drive(zip_id, local_zip, file_size=zip_size)
    unzip_articles(file_path=zip_path)
    if rm_metadata:
        os.remove(metadata_path)


def create_test_plos_corpus(corpusdir=corpusdir):
    """
    Downloads a copy of 10,000 randomly selected PLOS articles by:
    1) creating corpusdir if it doesn't exist
    2) downloading the zip file (defaults to corpus directory)
    3) extracting the individual XML files into the corpus directory
    :param corpusdir: directory where the corpus is to be downloaded and extracted
    :return: None
    """
    if os.path.isdir(corpusdir) is False:
        os.mkdir(corpusdir)
        print('Creating folder for article xml')
    zip_path = download_file_from_google_drive(test_zip_id, local_test_zip)
    unzip_articles(file_path=zip_path, extract_directory=corpusdir)


def download_corpus_metadata_files(csv_abstracts=True, csv_no_abstracts=True, sqlitedb=True, destination=None):
    """Downloads up to three files of metadata generated from the PLOS Corpus XML.
    Includes two csvs and a sqlite database.
    """
    if destination is None:
        destination = os.getcwd()
    if csv_abstracts:
        csv_abstracts_id = '0B_JDnoghFeEKQWlNUUJtY1pIY3c'
        csv_abstracts_file = download_file_from_google_drive(csv_abstracts_id,
                                                             'allofplos_metadata_test.csv',
                                                             destination=destination)
    if csv_no_abstracts:
        csv_no_abstracts_id = '0B_JDnoghFeEKeEp6S0R2Sm1YcEk'
        csv_no_abstracts_file = download_file_from_google_drive(csv_no_abstracts_id,
                                                                'allofplos_metadata_no_abstracts_test.csv',
                                                                destination=destination)
    if sqlitedb:
        sqlitedb_id = '1gcQW7cc6Z9gDBu_vHxghNwQaMkyvVuMC'
        sqlitedb_file = download_file_from_google_drive(sqlitedb_id,
                                                        'ploscorpus_test.db.gz',
                                                        destination=destination)
        print("Extracting sqlite db...")
        inF = gzip.open(sqlitedb_file, 'rb')
        outF = open('ploscorpus_test.db', 'wb')
        outF.write(inF.read())
        inF.close()
        outF.close()
        print("Extraction complete.")





def main():
    """
    Entry point for the program. This is used when the program is used as a
    standalone script
    :return: None
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--plos', action='store_true', help=
                        'Used when inside the plos network')
    args = parser.parse_args()
    plos_network = False
    if args.plos:
        URL_TMP = INT_URL_TMP
        plos_network = True
    else:
        URL_TMP = EXT_URL_TMP
    # Step 0: Initialize first copy of repository]
    try:
        corpus_files = [name for name in os.listdir(corpusdir) if os.path.isfile(
                        os.path.join(corpusdir, name))]
    except FileNotFoundError:
        corpus_files = []
    if len(corpus_files) < min_files_for_valid_corpus:
        print('Not enough articles in corpusdir, re-downloading zip file')
        # TODO: check if zip file is in top-level directory before downloading
        create_local_plos_corpus()

    # Step 1: Query solr via URL and construct DOI list
        # Filtered by article type & scheduled for the last 14 days.
        # Returns specific URL query & the number of search results.
        # Parses the returned dictionary of article DOIs, removing common leading numbers, as a list.
        # Compares to list of existing articles in the PLOS corpus folder to create list of DOIs to download.
    dois_needed_list = get_dois_needed_list()

    # Step 2: Download new articles
        # For every doi in dois_needed_list, grab the accompanying XML from content-repo
        # If no new articles, don't run any other cells
        # Check if articles are uncorrected proofs
        # Check if corrected articles linked to new corrections articles are updated
        # Merge new XML into folder
        # If need to bulk download, please start here:
        # https://drive.google.com/open?id=0B_JDnoghFeEKLTlJT09IckMwOFk
    download_check_and_move(dois_needed_list,
                            uncorrected_proofs_text_list,
                            tempdir=newarticledir,
                            destination=corpusdir,
                            plos_network=plos_network)
    return None

if __name__ == "__main__":
    main()
