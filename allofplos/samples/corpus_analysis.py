"""
This set of functions is for analyzing all the articles in the PLOS corpus. A Jupyter Notebook is provided with
examples of analysis. It can:
    * compare the articles indexed in Solr, PMC, and article pages
    * spot-check individual JATS fields for irregularities
    * create summaries of articles by type, publication date, etc
    * generate lists of retracted or corrected articles
"""

import collections
import csv
import os
import random
import requests

from tqdm import tqdm

from .. import get_corpus_dir, newarticledir

from ..plos_regex import (validate_doi, full_doi_regex_match, validate_url, validate_filename)
from ..transformations import (filename_to_doi, doi_to_url)
from ..plos_corpus import (listdir_nohidden, uncorrected_proofs_text_list,
                           download_updated_xml, get_all_solr_dois,
                           download_check_and_move)
from ..article_class import Article

counter = collections.Counter
pmcdir = "pmc_articles"
max_invalid_files_to_print = 100


def validate_corpus(directory=None):
    """
    For every local article file and DOI listed on Solr, validate file names, DOIs, URLs in terms of
    regular expressions.
    Stops checking as soon as encounters problem and prints it
    :return: boolean of whether corpus passed validity checks
    """
    if directory is None:
        directory = get_corpus_dir()
    # check DOIs
    plos_dois = get_all_plos_dois()
    plos_valid_dois = [doi for doi in plos_dois if validate_doi(doi)]
    if set(plos_dois) == set(plos_valid_dois):
        pass
    else:
        print("Invalid DOIs: {}".format(set(plos_dois) - set(plos_valid_dois)))
        return False

    # check urls
    plos_urls = [doi_to_url(doi) for doi in plos_valid_dois]
    plos_valid_urls = [url for url in plos_urls if validate_url(url)]
    if set(plos_urls) == set(plos_valid_urls) and len(plos_valid_urls) == len(plos_valid_dois):
        pass
    else:
        print("Invalid URLs: {}".format(set(plos_urls) - set(plos_valid_urls)))
        return False

    # check files and filenames
    plos_files = listdir_nohidden(directory)
    if plos_files:
        plos_valid_filenames = [article for article in plos_files if validate_filename(article)]
        if len(plos_valid_dois) == len(plos_valid_filenames):
            pass
        else:
            print("Invalid filenames: {}".format(set(plos_valid_dois) - set(plos_valid_filenames)))
            return False
        plos_valid_files = [article for article in plos_valid_filenames if os.path.isfile(article)]
        if set(plos_valid_filenames) == set(plos_valid_files):
            return True
        else:
            invalid_files = set(plos_valid_filenames) - set(plos_valid_files)
            if len(invalid_files) > max_invalid_files_to_print:
                print("Too many invalid files to print: {}".format(len(invalid_files)))
            else:
                print("Invalid files: {}".format(invalid_files))
            return False
    else:
        print("Corpus directory empty. Re-download by running create_local_plos_corpus()")
        return False

# These functions are for getting the article types of all PLOS articles.


def get_jats_article_type_list(article_list=None, directory=None):
    """Makes a list of of all JATS article types in the corpus

    Sorts them by frequency of occurrence
    :param article_list: list of articles, defaults to None
    :param directory: directory of articles, defaults to get_corpus_dir()
    :returns: dictionary with each JATS type matched to number of occurrences
    :rtype: dict
    """
    if directory is None:
        directory = get_corpus_dir()
    if article_list is None:
        article_list = listdir_nohidden(directory)

    jats_article_type_list = []

    for article_file in tqdm(article_list):
        article = Article.from_filename(article_file, directory=directory)
        jats_article_type_list.append(article.type_)

    print(len(set(jats_article_type_list)), 'types of articles found.')
    article_types_structured = counter(jats_article_type_list).most_common()
    return article_types_structured


def get_plos_article_type_list(article_list=None, directory=None):
    """Makes a list of of all internal PLOS article types in the corpus

    Sorts them by frequency of occurrence
    :param article_list: list of articles, defaults to None
    :param directory: directory of articles, defaults to get_corpus_dir()
    :returns: dictionary with each PLOS type matched to number of occurrences
    :rtype: dict
    """
    if directory is None:
        directory = get_corpus_dir()
    if article_list is None:
        article_list = listdir_nohidden(directory)

    PLOS_article_type_list = []

    for article_file in tqdm(article_list):
        article = Article.from_filename(article_file, directory=directory)
        PLOS_article_type_list.append(article.plostype)

    print(len(set(PLOS_article_type_list)), 'types of articles found.')
    PLOS_article_types_structured = counter(PLOS_article_type_list).most_common()
    return PLOS_article_types_structured


def get_article_types_map(article_list=None, directory=None):
    """Maps the JATS and PLOS article types onto the XML DTD.

    Used for comparing how JATS and PLOS article types are assigned
    :param article_list: list of articles, defaults to None
    :param directory: directory of articles, defaults to get_corpus_dir()
    :returns: list of tuples of JATS, PLOS, DTD for each article in the corpus
    :rtype: list
    """
    if directory is None:
        directory = get_corpus_dir()
    if article_list is None:
        article_list = listdir_nohidden(directory)
    article_types_map = []
    for i, article_file in tqdm(article_list):
        article = Article.from_filename(article_file)
        article.directory = directory
        types = [article.type_, article.plostype, article.dtd]
        types = tuple(types)
        article_types_map.append(types)
    return article_types_map


def article_types_map_to_csv(article_types_map):
    """put the `get_article_types_map.()` list of tuples into a csv.

    :param article_types_map: output of `get_article_types_map()`
    """
    with open('articletypes.csv', 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['type', 'count'])
        for row in article_types_map:
            csv_out.writerow(row)


# These functions are for getting retracted articles


def get_retracted_doi_list(article_list=None, directory=None):
    """
    Scans through articles in a directory to see if they are retraction notifications,
    scans articles that are that type to find DOIs of retracted articles
    :return: tuple of lists of DOIs for retractions articles, and retracted articles
    """
    if directory is None:
        directory = get_corpus_dir()
    retractions_doi_list = []
    retracted_doi_list = []
    if article_list is None:
        article_list = listdir_nohidden(directory)
    for art in tqdm(article_list):
        article = Article.from_filename(art)
        article.directory = directory
        if article.type_ == 'retraction':
            retractions_doi_list.append(article.doi)
            # Look in those articles to find actual articles that are retracted
            retracted_doi_list.extend(article.related_dois)
            # check linked DOI for accuracy
            for doi in article.related_dois:
                if bool(full_doi_regex_match.search(doi)) is False:
                    print("{} has incorrect linked DOI field: '{}'".format(art, doi))
    print(len(retracted_doi_list), 'retracted articles found.')
    return retractions_doi_list, retracted_doi_list


def get_amended_article_list(article_list=None, directory=None):
    """
    Scans through articles in a directory to see if they are amendment notifications,
    scans articles that are that type to find DOI substrings of amended articles
    :param article: the filename for a single article
    :param directory: directory where the article file is, default is get_corpus_dir()
    :return: list of DOIs for articles issued a correction
    """
    if directory is None:
        directory = get_corpus_dir()
    amendments_article_list = []
    amended_article_list = []
    if article_list is None:
        article_list = listdir_nohidden(directory)

    # check for amendments article type
    for art in tqdm(article_list):
        article = Article.from_filename(art)
        article.directory = directory
        if article.amendment:
            amendments_article_list.append(article.doi)
            # get the linked DOI of the amended article
            amended_article_list.extend(article.related_dois)
            # check linked DOI for accuracy
            for doi in article.related_dois:
                if bool(full_doi_regex_match.search(doi)) is False:
                    print(article.doi, "has incorrect linked DOI:", doi)
    print(len(amended_article_list), 'amended articles found.')
    return amendments_article_list, amended_article_list


# These functions are for checking for silent XML updates

def create_pubdate_dict(directory=None):
    """
    For articles in directory, create a dictionary mapping them to their pubdate.
    Used for truncating the revisiondate_sanity_check to more recent articles only
    :param directory: directory of articles
    :return: a dictionary mapping article files to datetime objects of their pubdates
    """
    if directory is None:
        directory = get_corpus_dir()
    articles = listdir_nohidden(directory)
    pubdates = {art: Article.from_filename(art).pubdate for art in articles}
    return pubdates


def revisiondate_sanity_check(article_list=None, tempdir=newarticledir, directory=None, truncated=True):
    """
    :param truncated: if True, restrict articles to only those with pubdates from the last year or two
    """
    if directory is None:
        directory = get_corpus_dir()
    list_provided = bool(article_list)
    if article_list is None and truncated is False:
        article_list = listdir_nohidden(directory)
    if article_list is None and truncated:
        pubdates = create_pubdate_dict(directory=directory)
        article_list = sorted(pubdates, key=pubdates.__getitem__, reverse=True)
        article_list = article_list[:30000]

    try:
        os.mkdir(tempdir)
    except FileExistsError:
        pass
    articles_different_list = []
    for article_file in tqdm(article_list):
        updated = download_updated_xml(article_file=article_file)
        if updated:
            articles_different_list.append(article_file)
        if list_provided:
            article_list.remove(article_file)  # helps save time if need to restart process
    print(len(article_list), "article checked for updates.")
    print(len(articles_different_list), "articles have updates.")
    return articles_different_list


def check_solr_doi(doi):
    '''
    For an article doi, see if there's a record of it in Solr.
    :rtype: bool
    '''
    solr_url = 'http://api.plos.org/search?q=*%3A*&fq=doc_type%3Afull&fl=id,&wt=json&indent=true&fq=id:%22{}%22'.format(doi)
    article_search = requests.get(solr_url).json()
    return bool(article_search['response']['numFound'])


def get_all_local_dois(directory=None):
    """Get all local DOIs in a corpus directory.

    :param directory: directory of articles, defaults to get_corpus_dir()
    :returns: list of DOIs
    :rtype: list
    """
    if directory is None:
        directory = get_corpus_dir()
    local_dois = [filename_to_doi(art) for art in listdir_nohidden(directory)]
    return local_dois


def get_all_plos_dois(local_articles=None, solr_articles=None):
    '''
    Collects lists of articles for local and solr, calculates the difference.
    Missing local downloads easily solved by re-running plos_corpus.py.
    Missing solr downloads require attention.
    :return: every DOI in PLOS corpus, across local and remote versions
    '''
    if solr_articles is None:
        solr_articles = get_all_solr_dois()
    if local_articles is None:
        local_articles = get_all_local_dois()
    missing_local_articles = set(solr_articles) - set(local_articles)
    if missing_local_articles:
        print('re-run plos_corpus.py to download latest {0} PLOS articles locally.'
              .format(len(missing_local_articles)))
    missing_solr_articles = set(local_articles) - set(solr_articles)
    plos_articles = set(solr_articles + local_articles)
    if missing_solr_articles:
        print('\033[1m' + 'Articles that needs to be re-indexed on Solr:')
        print('\033[0m' + '\n'.join(sorted(missing_solr_articles)))

    return plos_articles


def get_random_list_of_dois(directory=None, count=100):
    '''
    Gets a list of random DOIs. Tries first to construct from local files in
    directory, otherwise tries Solr DOI list as backup.
    :param directory: defaults to get_corpus_dir()
    :param count: specify how many DOIs are to be returned
    :return: a list of random DOIs for analysis
    '''
    if directory is None:
        directory = get_corpus_dir()
    try:
        article_list = listdir_nohidden(directory)
        sample_file_list = random.sample(article_list, count)
        sample_doi_list = [filename_to_doi(f) for f in sample_file_list]
    except OSError:
        doi_list = get_all_solr_dois()
        sample_doi_list = random.sample(doi_list, count)
    return sample_doi_list


def get_article_metadata(article_file, size='small'):
    """
    For an individual article in the PLOS corpus, create a tuple of a set of metadata fields sbout that corpus.
    Make it small, medium, or large depending on number of fields desired.
    :param article_file: individual local PLOS XML article
    :param size: small, medium or large, aka how many fields to return for each article
    :return: tuple of metadata fields tuple, wrong_date_strings dict
    """
    article = Article.from_filename(article_file)
    doi = article.doi
    filename = os.path.basename(article.filename).rstrip('.xml')
    title = article.title
    journal = article.journal
    jats_article_type = article.type_
    plos_article_type = article.plostype
    dtd_version = article.dtd
    dates = article.get_dates()
    (pubdate, collection, received, accepted, revdate) = ('', '', '', '', '')
    pubdate = article.pubdate
    revdate = article.revdate
    counts = article.counts
    (fig_count, table_count, page_count) = ('', '', '')
    body_word_count = article.word_count
    related_articles = article.related_dois
    abstract = article.abstract
    try:
        collection = dates['collection']
    except KeyError:
        pass
    try:
        received = dates['received']
    except KeyError:
        pass
    try:
        accepted = dates['accepted']
    except KeyError:
        pass
    try:
        fig_count = counts['fig-count']
    except KeyError:
        pass
    try:
        table_count = counts['table-count']
    except KeyError:
        pass
    try:
        page_count = counts['page-count']
    except KeyError:
        pass
    metadata = [doi, filename, title, journal, jats_article_type, plos_article_type, dtd_version, pubdate, revdate, received,
                accepted, collection, fig_count, table_count, page_count, body_word_count, related_articles, abstract]
    metadata = tuple(metadata)
    if len(metadata) == 18:
        return metadata
    else:
        print('Error in {}: {} items'.format(article_file, len(metadata)))
        return False


def get_corpus_metadata(article_list=None, directory=None):
    """
    Run get_article_metadata() on a list of files, by default every file in directory 
    Includes a progress bar
    
    TODO: this does not return a tuple, other parts of the code expect it to return a tuple, and its docs expect a tuple

    :param article_list: list of articles to run it on
    :return: list of tuples for each article; list of dicts for wrong date orders
    """
    if directory is None:
        directory = get_corpus_dir()
    if article_list is None:
        article_list = listdir_nohidden(directory)
    corpus_metadata = []
    for article_file in tqdm(article_list):
        metadata = get_article_metadata(article_file)
        corpus_metadata.append(metadata)
    return corpus_metadata


def corpus_metadata_to_csv(corpus_metadata=None,
                           article_list=None,
                           wrong_dates=None,
                           csv_file='allofplos_metadata.csv',
                           directory=None
                           ):
    """
    Convert list of tuples from get_article_metadata to csv
    :param corpus_metadata: the list of tuples, defaults to None
    :param article_list: TODO: needs documentation, defaults to None
    :param wrong_dates: TODO: needs documentation, defaults to None
    :csv_file: string, TODO: needs more documentation, defaults to 'allofplos_metadata.csv'
    :directory: 
    :return: None
    """
    if directory is None:
        directory = get_corpus_dir()
    if corpus_metadata is None:
        corpus_metadata, wrong_dates = get_corpus_metadata(article_list, directory=directory)
    # write main metadata csv file
    with open(csv_file, 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['doi', 'filename', 'title', 'journal', 'jats_article_type', 'plos_article_type',
                          'dtd_version', 'pubdate', 'revdate', 'received', 'accepted', 'collection', 'fig_count', 'table_count',
                          'page_count', 'body_word_count', 'related_article', 'abstract'])
        for row in corpus_metadata:
            csv_out.writerow(row)
    # write wrong dates csv file, with longest dict providing the keys
    if wrong_dates:
        keys = max(wrong_dates, key=len).keys()
        with open('wrong_dates.csv', 'w') as out:
            dict_writer = csv.DictWriter(out, keys)
            dict_writer.writeheader()
            dict_writer.writerows(wrong_dates)


def read_corpus_metadata_from_csv(csv_file='allofplos_metadata.csv'):
    """
    reads in a csv of data, excluding the header row
    :param csv_file: csv file of data, defaults to 'allofplos_metadata.csv'
    :return: list of tuples of article metadata
    """
    with open(csv_file, 'r') as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)
        corpus_metadata = [tuple(line) for line in reader]
    return corpus_metadata


def update_corpus_metadata_csv(csv_file='allofplos_metadata.csv', comparison_dois=None, directory=None):
    """
    Incrementally update the metadata of PLOS articles in the csv file
    :param csv_file: csv file of data, defaults to 'allofplos_metadata.csv'
    :comparison_dois: list of DOIs to check whether their metadats is included
    return updated corpus metadata
    """
    if directory is None:
        directory = get_corpus_dir()
    # Step 1: get metadata and DOI list from existing csv file
    try:
        corpus_metadata = read_corpus_metadata_from_csv(csv_file)
        csv_doi_list = [row[0] for row in corpus_metadata]
    except FileNotFoundError:
        corpus_metadata = []
        csv_doi_list = []
    # Step 2: compare DOI list with master list
    if comparison_dois is None:
        comparison_dois = get_all_solr_dois()
    dois_needed_list = list(set(comparison_dois) - set(csv_doi_list))
    # Step 3: compare to local file list
    local_doi_list = [filename_to_doi(article_file) for article_file in listdir_nohidden(directory)]
    files_needed_list = list(set(dois_needed_list) - set(local_doi_list))
    if files_needed_list:
        print('Local corpus must be updated before .csv metadata can be updated.\nUpdating local corpus now')
        download_check_and_move(files_needed_list,
                                uncorrected_proofs_text_list,
                                tempdir=newarticledir,
                                destination=directory)

    # Step 4: append new data to existing list
    new_corpus_metadata, wrong_dates = get_corpus_metadata(article_list=dois_needed_list)
    corpus_metadata.extend(new_corpus_metadata)
    # Step 5: write new dataset to .csv
    corpus_metadata_to_csv(corpus_metadata=corpus_metadata, csv_file='allofplos_metadata_updated.csv')
    return corpus_metadata
