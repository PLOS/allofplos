import datetime
import hashlib

import requests

BLOCKSIZE = 65536
hasher = hashlib.sha256()


def hash_file(fname):
    """ Create a SHA-256 hash for an article file in the corpus directory.

    Used in `Corpus().hashtable()`. Takes a full filepath.
    :return: SHA-256 hexcode for a file
    """
    with open(fname, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
        file_hash = hasher.hexdigest()

    return file_hash


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
