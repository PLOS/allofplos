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
Update by downloading articles from journal pages if local store is not complete
Check for and download amended articles that have been issued amendments
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
import requests
from tqdm import tqdm

from .. import get_corpus_dir, newarticledir, uncorrected_proofs_text_list

from ..plos_regex import validate_doi
from ..transformations import (BASE_URL_API, filename_to_doi, doi_to_path, doi_to_url)
from ..article_class import Article
from .gdrive import (download_file_from_google_drive, get_zip_metadata, unzip_articles,
                     ZIP_ID, LOCAL_ZIP, LOCAL_TEST_ZIP, TEST_ZIP_ID, min_files_for_valid_corpus)

help_str = "This program downloads a zip file with all PLOS articles and checks for updates"

# Making sure DS.Store not included as file
ignore_func = shutil.ignore_patterns('.DS_Store')

# Some example URLs that may be useful
EXAMPLE_SEARCH_URL = ('http://api.plos.org/search?q=*%3A*&fq=doc_type%3Afull&fl=id,'
                      '&wt=json&indent=true&fq=article_type:"research+article"+OR+article_type:"correction"+OR+'
                      'article_type:"meta-research+article"&sort=%20id%20asc&'
                      'fq=publication_date:%5B2017-03-05T00:00:00Z+TO+2017-03-19T23:59:59Z%5D&start=0&rows=1000')

# Starting out list of needed articles as empty
dois_needed_list = []


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
        file_list = [os.path.join(path, f) for f in os.listdir(path)
                     if f.endswith(extension) and 'DS_Store' not in f]
    else:
        file_list = [f for f in os.listdir(path) if f.endswith(extension) and
                     'DS_Store' not in f]
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
    solr_search_results = []
    while(start < num_results):
        query_url = ''.join(howmanyarticles_url_base) + '&start=' + str(start) + '&rows=' + str(rows)
        article_search = requests.get(query_url).json()
        solr_partial_results = [x[item] for x in article_search["response"]["docs"]]
        solr_search_results.extend(solr_partial_results)
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


def get_dois_needed_list(comparison_list=None, directory=None):
    """
    Takes result of query from get_all_solr_dois and compares to local article directory.
    :param comparison_list: Defaults to creating a full list of local article files.
    :param directory: An int value indicating the first row of results to return
    :return: A list of DOIs for articles that are not in the local article directory.
    """
    if comparison_list is None:
        comparison_list = get_all_solr_dois()
    if directory is None:
        directory = get_corpus_dir()

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


def repo_download(dois, tempdir, ignore_existing=True):
    """
    Downloads a list of articles by DOI from PLOS's journal pages to a temporary directory
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
        existing_articles = [filename_to_doi(f) for f in listdir_nohidden(tempdir)]
        dois = set(dois) - set(existing_articles)

    for doi in tqdm(sorted(dois), disable=None):
        url = doi_to_url(doi)
        articleXML = et.parse(url)
        article_path = doi_to_path(doi, directory=tempdir)
        # create new local XML files
        if ignore_existing is False or ignore_existing and os.path.isfile(article_path) is False:
            with open(article_path, 'w', encoding='utf8') as f:
                f.write(et.tostring(articleXML, method='xml', encoding='unicode'))
                time.sleep(.5)

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


def compare_article_pubdate(doi, days=22, directory=None):
    """
    Check if an article's publication date was more than 3 weeks ago.
    :param doi: doi of the article
    :param days: how long ago to compare the publication date (default 22 days)
    :param directory: directory the article file is located in (defaults to get_corpus_dir())
    :return: boolean for whether the pubdate was older than the days value
    """
    if directory is None:
        directory = get_corpus_dir()
    article = Article(doi, directory=directory)
    try:
        pubdate = article.pubdate
        today = datetime.datetime.now()
        three_wks_ago = datetime.timedelta(days)
        compare_date = today - three_wks_ago
        return pubdate < compare_date
    except ValueError:
        print("Pubdate error in {}".format(doi))


def download_xml(doi, tempdir=newarticledir):
    """For a given DOI, download its remote XML file to tempdir."""
    art = Article(doi, directory=tempdir)
    with open(art.filename, 'w', encoding='utf8') as f:
        f.write(art.get_remote_xml())
    return art


def download_updated_xml(article_file,
                         tempdir=newarticledir):
    """
    For an article file, compare local XML to remote XML
    If they're different, download new version of article
    :param article_file: the filename for a single article
    :param tempdir: directory where files are downloaded to
    :param vor_check: whether checking to see if uncorrected proof is updated
    :return: boolean for whether update was available & downloaded
    """
    article = Article.from_filename(article_file)
    try:
        os.mkdir(tempdir)
    except FileExistsError:
        pass
    articleXML_remote = article.get_remote_xml()
    if not article_file.endswith('.xml'):
        article_file += '.xml'
    try:
        articleXML_local = article.xml
    except OSError:
        article.directory = newarticledir
        articleXML_local = article.xml

    if articleXML_remote == articleXML_local:
        updated = False
    else:
        article_new = download_xml(article.doi, tempdir=tempdir)
        updated = True
    return updated


def check_for_amended_articles(directory=newarticledir, article_list=None):
    """
    For articles in the temporary download directory, check if article_type is an amendment
    If amendment, surface the DOI of the article being amended
    Use with `download_amended_articles`
    For more information about the amendment type, see `amendment` in the Article class
    :param article: the filename for a single article
    :param directory: directory where the article file is, default is newarticledir
    :return: list of filenames to existing local files for articles issued an amendment
    """
    amended_doi_list = []
    if article_list is None:
        article_list = listdir_nohidden(directory)
    for article_file in article_list:
        article = Article.from_filename(article_file)
        article.directory = directory
        if article.amendment:
            amended_doi_list.extend(article.related_dois)
    amended_article_list = [Article(doi).filename if Article(doi).local else
                            doi_to_path(doi, directory=directory) for doi in list(amended_doi_list)]
    print(len(amended_article_list), 'amended articles found.')
    return amended_article_list


def download_amended_articles(directory=None, tempdir=newarticledir, amended_article_list=None):
    """For a list of articles that have been amended, check if the xml was also updated.

    Use with `check_for_amended_articles`
    Many amendments don't result in XML changes
    For more information about the amendment type, see `amendment` in the Article class
    :param article: the filename for a single article
    :param directory: directory where the article file is, default is newarticledir
    :param tempdir: where new articles are downloaded to-
    :return: list of DOIs for articles downloaded with new XML versions
    """
    if directory is None:
        directory = get_corpus_dir()
    if amended_article_list is None:
        amended_article_list = check_for_amended_articles(directory)
    amended_updated_article_list = []
    print("Checking amended articles...")
    for article in tqdm(amended_article_list, disable=None):
        updated = download_updated_xml(article)
        if updated:
            amended_updated_article_list.append(article)
    print(len(amended_updated_article_list), 'amended articles downloaded with new xml.')
    return amended_updated_article_list


def get_uncorrected_proofs(directory=None, proof_filepath=uncorrected_proofs_text_list):
    """
    Loads the uncorrected proofs txt file.
    Failing that, creates new txt file from scratch using directory.
    :param directory: Directory containing the article files
    :return: set of DOIs of uncorrected proofs from text list
    """
    if directory is None:
        directory = get_corpus_dir()

    try:
        with open(proof_filepath) as f:
            uncorrected_proofs = set(f.read().splitlines())
    except FileNotFoundError:
        print("Creating new text list of uncorrected proofs from scratch.")
        article_files = listdir_nohidden(directory)
        uncorrected_proofs = set()
        for article_file in tqdm(article_files, disable=None, miniters=int(len(article_files)/1000)):
            article = Article.from_filename(article_file)
            article.directory = directory
            if article.proof == 'uncorrected_proof':
                uncorrected_proofs.add(article.doi)
        print("Saving uncorrected proofs.")
        with open(proof_filepath, 'w') as f:
            for item in tqdm(sorted(uncorrected_proofs), disable=None):
                f.write("%s\n" % item)
    return uncorrected_proofs


def check_for_uncorrected_proofs(directory=newarticledir, proof_filepath=uncorrected_proofs_text_list):
    """
    For a list of articles, check whether they are the 'uncorrected proof' type
    One of the checks on newly downloaded articles.
    :param proof_filepath: List of DOIs
    :param directory: Directory containing the article files
    :return: set of all DOIs that are uncorrected proofs, including from main article directory
    """

    # Read in uncorrected proofs from uncorrected_proofs_text_list txt file
    # If uncorrected_proofs txt file doesn't exist, build that set from scratch from main article directory
    uncorrected_proofs = get_uncorrected_proofs(proof_filepath=proof_filepath)

    # Check directory for uncorrected proofs
    # Append uncorrected proofs to running set
    if directory is None:
        directory = get_corpus_dir()
    articles = listdir_nohidden(directory)
    new_proofs = 0
    for article_file in articles:
        article = Article.from_filename(article_file)
        article.directory = directory
        if article.proof == 'uncorrected_proof':
            uncorrected_proofs.add(article.doi)
            new_proofs += 1
    # Copy all uncorrected proofs from list to clean text file
    with open(proof_filepath, 'w') as f:
        for item in sorted(uncorrected_proofs):
            f.write("%s\n" % item)
    if uncorrected_proofs:
        print("{} new uncorrected proofs found. {} total in set.".format(new_proofs, len(uncorrected_proofs)))
    else:
        print("No uncorrected proofs found in {} or in {}.".format(directory, proof_filepath))
    return uncorrected_proofs


def check_for_vor_updates(uncorrected_list=None):
    """
    For existing uncorrected proofs list,
    check whether a vor is available to download
    :param uncorrected_list: DOIs of uncorrected articles, default None
    :return: List of articles from uncorrected_list for which Solr says there is a new VOR waiting
    """

    # First get/make list of uncorrected proofs
    if uncorrected_list is None:
        uncorrected_list = list(get_uncorrected_proofs())
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
        print(len(vor_updates_available), "new VOR updates indexed in Solr.")
        logging.info("VOR updates to download.")
    else:
        print("No new VOR articles indexed in Solr.")
        logging.info("No new VOR articles in Solr")
    return vor_updates_available


def download_vor_updates(directory=None, tempdir=newarticledir,
                         vor_updates_available=None):
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
    if directory is None:
        directory = get_corpus_dir()
    if vor_updates_available is None:
        vor_updates_available = check_for_vor_updates()
    vor_updated_article_list = []
    for doi in tqdm(vor_updates_available, disable=None):
        updated = download_updated_xml(doi_to_path(doi), tempdir=tempdir)
        if updated:
            vor_updated_article_list.append(doi)

    old_uncorrected_proofs = get_uncorrected_proofs()
    new_uncorrected_proofs_list = list(old_uncorrected_proofs - set(vor_updated_article_list))

    # direct remote XML check; add their totals to totals above
    if new_uncorrected_proofs_list:
        proofs_download_list = remote_proofs_direct_check(article_list=new_uncorrected_proofs_list)
        vor_updated_article_list.extend(proofs_download_list)
        new_uncorrected_proofs_list = list(set(new_uncorrected_proofs_list) - set(vor_updated_article_list))
        too_old_proofs = [proof for proof in new_uncorrected_proofs_list if compare_article_pubdate(proof)]
        if too_old_proofs:
            print("Proofs older than 3 weeks: {}".format(too_old_proofs))

    # if any VOR articles have been downloaded, update static uncorrected proofs list
    if vor_updated_article_list:
        with open(uncorrected_proofs_text_list, 'w') as f:
            for item in sorted(new_uncorrected_proofs_list):
                f.write("%s\n" % item)
        print("{} uncorrected proofs updated to version of record.\n".format(len(vor_updated_article_list)) +
              "{} uncorrected proofs remaining in uncorrected proof list.".format(len(new_uncorrected_proofs_list)))

    else:
        print("No uncorrected proofs have a VOR update.")

    return vor_updated_article_list


def remote_proofs_direct_check(tempdir=newarticledir, article_list=None):
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
        article_list = list(get_uncorrected_proofs())
    print("Checking directly for additional VOR updates...")
    for doi in tqdm(article_list, disable=None):
        f = doi_to_path(doi)
        updated = download_updated_xml(f)
        if updated:
            proofs_download_list.append(doi)
    if proofs_download_list:
        print(len(proofs_download_list),
              "VOR articles directly downloaded.")
    else:
        print("No other new VOR articles found.")
    return proofs_download_list


def download_check_and_move(article_list, proof_filepath, tempdir, destination):
    """
    For a list of new articles to get, first download them from journal pages to the temporary directory
    Next, check these articles for uncorrected proofs and article_type amendments
    Act on available VOR updates & amended articles
    Then, move to corpus directory where the rest of the articles are
    :param article_list: List of new articles to download
    :param proof_filepath: List of uncorrected proofs to check for vor updates
    :param tempdir: Directory where articles to be downloaded to
    :param destination: Directory where new articles are to be moved to
    """
    repo_download(article_list, tempdir)
    amended_articles = check_for_amended_articles(directory=tempdir)
    download_amended_articles(amended_article_list=amended_articles)
    download_vor_updates()
    check_for_uncorrected_proofs(directory=tempdir)
    move_articles(tempdir, destination)


def create_local_plos_corpus(directory=None, rm_metadata=True):
    """
    Downloads a fresh copy of the PLOS corpus by:
    1) creating directory if it doesn't exist
    2) downloading metadata about the .zip of all PLOS XML
    2) downloading the zip file (defaults to corpus directory)
    3) extracting the individual XML files into the corpus directory
    :param directory: directory where the corpus is to be downloaded and extracted
    :param rm_metadata: COMPLETE HERE
    :return: None
    """
    if directory is None:
        directory = get_corpus_dir()
    if not os.path.isdir(directory):
        print('Creating folder for article xml')
    os.makedirs(directory, exist_ok=True)
    zip_date, zip_size, metadata_path = get_zip_metadata()
    zip_path = download_file_from_google_drive(ZIP_ID, LOCAL_ZIP, file_size=zip_size)
    unzip_articles(file_path=zip_path)
    if rm_metadata:
        os.remove(metadata_path)


def create_test_plos_corpus(directory=None):
    """
    Downloads a copy of 10,000 randomly selected PLOS articles by:
    1) creating directory if it doesn't exist
    2) downloading the zip file (defaults to corpus directory)
    3) extracting the individual XML files into the corpus directory
    :param directory: directory where the corpus is to be downloaded and extracted
    :return: None
    """
    if directory is None:
        directory = get_corpus_dir()
    if not os.path.isdir(directory):
        print('Creating folder for article xml')
    os.makedirs(directory, exist_ok=True)
    zip_path = download_file_from_google_drive(TEST_ZIP_ID, LOCAL_TEST_ZIP)
    unzip_articles(file_path=zip_path, extract_directory=directory)


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
