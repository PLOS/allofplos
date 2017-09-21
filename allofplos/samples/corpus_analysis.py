"""
This set of functions is for analyzing all the articles in the PLOS corpus. A Jupyter Notebook is provided with
examples of analysis. It can:
    * compare the articles indexed in Solr, PMC, and content-repo
    * spot-check individual JATS fields for irregularities
    * create summaries of articles by type, publication date, etc
    * generate lists of retracted or corrected articles
"""

import collections
import csv
import datetime
import lxml.etree as et
from glob import glob
from os.path import join
from os import (listdir, rmdir, mkdir)
import os
import re
import requests
from shutil import move, rmtree
import time

from download import download
import numpy as np

from plos_corpus import (listdir_nohidden, extract_filenames, check_article_type, get_articleXML_content,
                         get_related_article_doi, download_updated_xml, unzip_articles, get_all_solr_dois,
                         file_to_doi, doi_to_file, check_if_uncorrected_proof, newarticledir)

counter = collections.Counter
newpmcarticledir = "New_PMC_articles"
USER_EMAIL = 'elizabeth.seiver@gmail.com'

pmcdir = "PMC_Articles/"
corpusdir = 'allofplos_xml'
pmc_csv = 'doi_to_pmc.csv'
# xml URL takes PMC identifier minus 'PMC'
pmc_xml_url = 'https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:'
pmc_xml_url_suffix = '&metadataPrefix=pmc'
# can query up to 200 DOIs from PMC
pmc_doi_query_url = 'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=corpustest&email={0}&ids='.format(USER_EMAIL)
pmc_doi_query_url_suffix = '&versions=no&format=json'
pmc_pmcid_query_url = 'https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id='
pmc_allplos_query_url = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term='
                         '(((((((("PLoS+ONE"[Journal])+OR+"PLoS+Genetics"[Journal])+OR+"PLoS+Pathogens"[Journal])'
                         'OR+"PLoS+Neglected+Tropical+Diseases"[Journal])+OR+"PLoS+Computational+Biology"[Journal])'
                         'OR+"PLoS+Biology"[Journal])+OR+"PLoS+Medicine"[Journal])+OR+"plos+currents"[Journal])'
                         '+OR+"PLoS+Clinical+Trials"[Journal])&retmax=1000&retmode=json&tool=corpustest'
                         '&email={0}'.format(USER_EMAIL))
PMC_FTP_URL = 'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/'
pmc_file_list = 'oa_file_list.txt'
newpmcarticledir = "New_PMC_articles"


"""
The following RegEx pertains to the 7 main PLOS journals and the defunct PLOS Clinical Trials, as well as PLOS Currents.
"""

regex_match_prefix = r"^10\.1371/"
regex_body_match = (r"((journal\.p[a-zA-Z]{3}\.[\d]{7}$)"
                    r"|(annotation/[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}$))")
regex_body_currents = (r"((currents\.[a-zA-Z]{2,9}\.[a-zA-Z0-9]{32}$)"
                       r"|(currents\.RRN[\d]{4}$)"
                       r"|([a-zA-Z0-9]{13}$)"
                       r"|([a-zA-Z0-9]{32}$))")
full_doi_regex_match = re.compile(regex_match_prefix+regex_body_match)
full_doi_regex_search = re.compile(r"10\.1371/journal\.p[a-zA-Z]{3}\.[\d]{7}"
                                   "|10\.1371/annotation/[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}")
currents_doi_regex = re.compile(regex_match_prefix+regex_body_currents)


def make_regex_bool(match_or_none):
    return bool(match_or_none)


def validate_doi(string):
    """
    For an individual string, tests whether the full string is a valid PLOS DOI or not
    Example: '10.1371/journal.pbio.2000777' is True, but '10.1371/journal.pbio.2000777 ' is False
    :return: True if a valid PLOS DOI; False if not
    """
    return make_regex_bool(full_doi_regex_match.search(string))


def find_valid_dois(string):
    """
    For an individual string, searches for any valid PLOS DOIs within it and returns them
    :return: list of valid PLOS DOIs contained within string
    """
    return full_doi_regex_search.findall(string)


def show_invalid_dois(doi_list):
    """
    Checks to see whether a list of PLOS DOIs follow the correct format. Used mainly to determine
    if linked DOI fields in other articles (such as retractions and corrections) are correct.
    :return: list of DOI candidates that don't match PLOS's pattern
    """
    nonmatches = np.array([not validate_doi(x) for x in doi_list])
    return list(np.array(doi_list)[nonmatches])


def currents_doi_filter(doi_list):
    """
    Checks to see whether a list of PLOS Currents DOIs follow the correct format. Used mainly to determine
    if linked DOI fields in PMC articles are correct.
    :return: list of DOI candidates that don't match Currents' pattern
    """
    nonmatches = np.array([not make_regex_bool(currents_doi_regex.search(x)) for x in doi_list])
    return list(np.array(doi_list)[nonmatches])


# These functions are for getting the article types of all PLOS articles.


def get_jats_article_type_list(article_list=None, directory=corpusdir):
    if article_list is None:
        article_list = listdir_nohidden(directory)

    jats_article_type_list = []

    for article_file in article_list:
        jats_article_type = check_article_type(article_file=article_file)
        jats_article_type_list.append(jats_article_type)

    print(len(set(jats_article_type_list)), 'types of articles found.')
    article_types_structured = counter(jats_article_type_list).most_common()
    return article_types_structured


def get_plos_article_type(article_file):
    article_categories = get_articleXML_content(
                                article_file=article_file,
                                tag_path_elements=["/",
                                                   "article",
                                                   "front",
                                                   "article-meta",
                                                   "article-categories"])
    subject_list = article_categories[0].getchildren()

    for subject in subject_list:
        if subject.get('subj-group-type') == "heading":
            subject_instance = subject_list[i][0]
            s = ''
            for text in subject_instance.itertext():
                s = s + text
                PLOS_article_type = s
    return PLOS_article_type


def get_plos_article_type_list(article_list=None):

    if article_list is None:
        article_list = listdir_nohidden(corpusdir)

    PLOS_article_type_list = []

    for article_file in article_list:
        plos_article_type = get_plos_article_type(article_file)
        PLOS_article_type_list.append(plos_article_type)

    print(len(set(PLOS_article_type_list)), 'types of articles found.')
    PLOS_article_types_structured = counter(PLOS_article_type_list).most_common()
    return PLOS_article_types_structured


def get_article_dtd(article_file):
    try:
        dtd = get_articleXML_content(
                                    article_file=article_file,
                                    tag_path_elements=["/",
                                                       "article"])
        dtd = dtd[0].attrib['dtd-version']
    except KeyError:
        print('Error parsing DTD from', article_file)
        dtd = 'N/A'
    return dtd


# Get tuples of article types mapped for all PLOS articles
def get_article_types_map(directory=corpusdir):
    article_types_map = []
    article_files = listdir_nohidden(directory)
    for article_file in article_files:
        jats_article_type = check_article_type(article_file)
        plos_article_type = get_plos_article_type(article_file)
        dtd_version = get_article_dtd(article_file)
        types = [jats_article_type, plos_article_type, dtd_version]
        types = tuple(types)
        article_types_map.append(types)
    return article_types_map


# write article types map to .csv file
def article_types_map_to_csv(article_types_map):
    with open('articletypes.csv', 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['type', 'count'])
        for row in article_types_map:
            csv_out.writerow(row)


# Generate list of retracted articles
def check_if_retraction_article(article_file):
    """For a given article, checks to see whether it is of the article type 'correction'"""
    article_type = check_article_type(article_file)
    if article_type == "retraction":
        return True

    return False


def check_if_link_works(url):
    '''See if a link is valid (i.e., returns a '200' to the HTML request).
    Used for checking a URL to a PLOS article on journals.plos.org
    '''
    request = requests.get(url)
    if request.status_code == 200:
        return True
    elif request.status_code == 404:
        return False
    else:
        return 'error'


# These functions are for getting retracted articles


def get_related_retraction_article(article_file):
    """
    For a given retraction article, returns the DOI of the retracted article
    """
    if check_if_retraction_article(article_file=article_file):
        related_article, related_article_type = get_related_article_doi(article_file=article_file,
                                                                        corrected=False)
        if related_article_type == 'retracted-article':
            return related_article, related_article_type
        else:
            print('Accompanying retracted article not found for', article)


def get_retracted_doi_list(article_list=None, directory=corpusdir):
    """
    Scans through articles in a directory to see if they are retraction notifications,
    scans articles that are that type to find DOIs of retracted articles
    :return: tuple of lists of DOIs for retractions articles, and retracted articles
    """
    retractions_doi_list = []
    retracted_doi_list = []
    if article_list is None:
        article_list = listdir_nohidden(directory)
    for article_file in article_list:
        if check_if_retraction_article(article_file):
            retractions_doi_list.append(file_to_doi(article_file))
            # Look in those articles to find actual articles that are retracted
            retracted_doi = get_related_retraction_article(article_file)[0]
            retracted_doi_list.append(retracted_doi)
            # check linked DOI for accuracy
            if make_regex_bool(full_doi_regex_match.search(retracted_doi)) is False:
                print("{} has incorrect linked DOI field: '{}'".format(article_file, retracted_doi))
    if len(retractions_doi_list) == len(retracted_doi_list):
        print(len(retracted_doi_list), 'retracted articles found.')
    else:
        print('Number of retraction articles and retracted articles are different: ',
              '{} vs. {}'.format(len(retractions_article_list), len(retracted_article_list)))
    return retractions_doi_list, retracted_doi_list


def get_corrected_article_list(article_list=None, directory=corpusdir):
    """
    Scans through articles in a directory to see if they are correction notifications,
    scans articles that are that type to find DOI substrings of corrected articles
    :param article: the filename for a single article
    :param directory: directory where the article file is, default is corpusdir
    :return: list of DOIs for articles issued a correction
    """
    corrections_article_list = []
    corrected_article_list = []
    if article_list is None:
        article_list = listdir_nohidden(directory)

    # check for corrections article type
    for article_file in article_list:
        article_type = check_article_type(article_file)
        if article_type == 'correction':
            corrections_article_list.append(article_file)
            # get the linked DOI of the corrected article
            corrected_article = get_related_article_doi(article_file, corrected=True)[0]
            corrected_article_list.append(corrected_article)
            # check linked DOI for accuracy
            if make_regex_bool(full_doi_regex_match.search(corrected_article)) is False:
                print(article_file, "has incorrect linked DOI:", corrected_article)
    print(len(corrected_article_list), 'corrected articles found.')
    return corrections_article_list, corrected_article_list


# These functions are for checking for silent XML updates

def create_pubdate_dict(directory=corpusdir):
    """
    For articles in directory, create a dictionary mapping them to their pubdate.
    Used for truncating the revisiondate_sanity_check to more recent articles only
    :return: a dictionary mapping article files to datetime objects of their pubdates
    """
    articles = listdir_nohidden(directory)
    pubdates = {article: get_article_pubdate(article) for article in articles}
    return pubdates


def revisiondate_sanity_check(article_list=None, tempdir=newarticledir, directory=corpusdir, truncated=True):
    """
    :param truncated: if True, restrict articles to only those with pubdates from the last year or two
    """
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
    for article_file in article_list:
        updated = download_updated_xml(article_file=article_file)
        if updated:
            articles_different_list.append(article_file)
    print(len(article_list), "article checked for updates.")
    print(len(articles_different_list), "articles have updates.")
    return articles_different_list


# These functions are for getting & analyzing the PLOS Corpus from PMC

def get_pmc_articles():
    """
    :return: a list of all article files in PMC folder
    """
    # step 1: download tarball file if needed
    pmc_url = 'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/articles.O-Z.xml.tar.gz'
    pmcdir = 'PMC_articles/'
    pmc_local_tar = 'PMC_files.tar.gz'
    pmc_path = os.path.join(pmcdir, pmc_local_tar)
    if os.path.isdir(pmcdir) is False:
        os.mkdir(pmcdir)
        print('Creating folder for PMC article xml')

    if len([name for name in os.listdir(pmcdir) if os.path.isfile(os.path.join(pmcdir, name))]) < 200000:
        print('Not enough articles in pmcdir, re-downloading zip file')
        path = download(pmc_url, pmc_path)

        # Step 2: unzip archive
        unzip_articles(directory=pmcdir, filetype='tar', file=pmc_local_tar)

        # Step 3: delete non-PLOS folders
        listdirs = glob("PMC_articles/*/")
        print(len(listdirs), "folders for all O-Z journals")
        for directory in list(listdirs):
            if directory.lower().startswith('pmc_articles/plos') is False:
                rmtree(directory)
                listdirs.remove(directory)
        print(len(listdirs), "folders remaining for PLOS journals")

        # Step 4: put all PLOS articles in higher level pmcdir folder & flatten hierarchy
        root = pmcdir
        print("moving PMC articles to top-level folder")
        for dirrr in list(listdirs):
            files = [f for dp, dn, filenames in os.walk(dirrr) for f in filenames if os.path.splitext(f)[1] == '.nxml']
            for file in files:
                move(join(dirrr, file), join(root, file))
            rmtree(dirrr)
    pmc_articles = listdir_nohidden(pmcdir, extension='.nxml')

    return pmc_articles


def get_article_doi(article_file):
    raw_xml = get_articleXML_content(article_file=article_file,
                                     tag_path_elements=["/",
                                                        "article",
                                                        "front",
                                                        "article-meta",
                                                        "article-id"])
    for x in raw_xml:
        for name, value in x.items():
            if value == 'doi':
                doi = x.text
                break
    return doi


def article_doi_sanity_check(directory=corpusdir, article_list=None, source='solr'):
    """
    For every article in a directory, make sure that the DOI field is both valid and matches
    the file name, if applicable. Prints invalid DOIs that don't match regex.
    :return: list of articles where the filename does not match the linked DOI
    """
    messed_up_articles = []
    if article_list is None:
        if source == 'PMC':
            article_list = listdir_nohidden(pmcdir, extension='.nxml')
        elif source == 'solr':
            article_list = listdir_nohidden(corpusdir)
    doifile_dict = {get_article_doi(article_file=article_file): article_file for article_file in article_list}
    doi_list = list(doifile_dict.keys())
    # check for PLOS regular regex
    bad_doi_list = [doi for doi in full_doi_filter(doi_list) if doi is not False]
    # check for Currents regex if PMC
    if bad_doi_list:
        if directory == pmcdir or source == 'PMC':
            bad_doi_list = currents_doi_filter(bad_doi_list)
    for doi in bad_doi_list:
        print("{} has invalid DOI field: '{}'".format(doifile_dict[doi], doi))
    if directory == corpusdir or source == 'solr':
        messed_up_articles = [doifile_dict[doi] for doi in doi_list if file_to_doi(doifile_dict[doi]) != doi]
        if len(messed_up_articles) == 0:
            print('All article file names match DOIs.')
        else:
            print(len(messed_up_articles), 'article files have DOI errors.')
        return messed_up_articles
    return bad_doi_list


def get_articles_by_doi_field(directory=pmcdir, article_list=None, check_new=True):
    doi_to_pmc = {}
    if directory == pmcdir and article_list is None:
        article_list = get_pmc_articles()
    elif article_list is None:
        article_list = listdir_nohidden(directory)
        if article_list == 0:
            article_list = listdir_nohidden(directory, extension='.nxml')

    if directory != pmcdir:
        for article in article_list:
            doi = get_article_doi(article_file=article)
            doi_to_pmc[doi] = article
    else:
        try:
            # read doi_to_pmc dict from csv
            with open(pmc_csv, 'r') as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)
                doi_to_pmc = dict(reader)

            scratch = False
            n = 0
            if check_new:
                for article in article_list:
                    if article not in doi_to_pmc.values():
                        doi = get_article_doi(article)
                        doi_to_pmc[doi] = os.path.basename(article).rstrip('.nxml').rstrip('.xml')
                        n = n + 1
                if n:
                    print(n, 'DOI/PMCID pairs added to dictionary.')

        except FileNotFoundError:
            print('Creating doi_to_pmc dictionary from scratch.')
            scratch = True
            n = 0
            file_list = listdir_nohidden(pmcdir, extension='.nxml')
            doi_to_pmc = {get_article_doi(pmc_file): os.path.basename(pmc_file).rstrip('.nxml') for pmc_file in file_list}
        # write doi_to_pmc dict to csv
        if scratch or n > 0:
            with open(pmc_csv, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(['DOI', 'PMC ID'])
                for key, value in doi_to_pmc:
                    writer.writerow([key, value])
            print('DOI, PMC ID list exported to', pmc_csv)

    return doi_to_pmc


def get_article_pubdate(article_file, date_format='%d %m %Y'):
    day = ''
    month = ''
    year = ''
    raw_xml = get_articleXML_content(article_file=article_file,
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
    try:
        pubdate = get_article_pubdate(article)
        today = datetime.datetime.now()
        three_wks_ago = datetime.timedelta(days)
        compare_date = today - three_wks_ago
        return pubdate < compare_date
    except OSError:
        pass


def check_solr_doi(doi):
    '''
    For an article doi, see if there's a record of it in Solr.
    '''
    solr_url = 'http://api.plos.org/search?q=*%3A*&fq=doc_type%3Afull&fl=id,&wt=json&indent=true&fq=id:%22{}%22'.format(doi)
    article_search = requests.get(solr_url).json()
    if article_search['response']['numFound'] > 0:
        return True
    else:
        return False


def get_pmc_doi_dict(id_list=None, chunk_size=150):
    '''
    Using the PMC ID query API, return the accompanying PMCID for each identifier in a given list.
    Can (ostensibly) query up to 200 identifiers at a time. Can accept lists of DOIs or PMC IDs
    :return: tuple of dictionary mapping DOI to PMCID, list of DOIs not found in PMC
    '''
    if id_list is None:
        id_list = extract_filenames(pmcdir, extension='.nxml')
    doi_to_pmc = {}
    dois_not_in_pmc = []
    # Make chunks of 200 DOIs at a time
    list_chunks = [id_list[x:x+chunk_size] for x in range(0, len(id_list), chunk_size)]
    for chunk in list_chunks:
        pmc_doi_string = ','.join(chunk)
        # Create the search URL
        pmc_doi_query = pmc_doi_query_url + pmc_doi_string
        # Parse the results & create dict entry for each result
        pmc_response = requests.get(pmc_doi_query)
        if pmc_response.status_code == 500:
            print('Error for DOI chunk; retry with smaller chunk size')
        else:
            pmc_results = et.XML(pmc_response.content)
            pmc_results = pmc_results.getchildren()[1:]  # exclude echo header
            for result in pmc_results:
                doi = result.attrib['doi']
                try:
                    pmcid = result.attrib['pmcid']
                    doi_to_pmc[doi] = pmcid
                except KeyError:
                    if result.attrib['status'] == 'error':
                        dois_not_in_pmc.append(doi)
                    else:
                        print('Weird error for', doi)
        time.sleep(1)
    return doi_to_pmc, dois_not_in_pmc


def update_pmc_dict_by_doi(id_list):
    '''
    With a list of identifiers, query PMC ID service to check for PMCIDs for articles. Print to .csv
    :return: tuple of full dictionary of DOIs to PMC IDs, DOIs without matching PMCIDs
    '''
    doi_to_pmc = get_articles_by_doi_field(check_new=False)
    doi_to_pmc2, dois_not_in_pmc = get_pmc_doi_dict(id_list)
    full_pmc_dict = {**doi_to_pmc2, **doi_to_pmc}
    with open(pmc_csv, 'w') as file:
        writer = csv.writer(file)
        writer.writerow(['DOI', 'PMC ID'])
        for key, value in full_pmc_dict.items():
            writer.writerow([key, value])
    return full_pmc_dict, dois_not_in_pmc


def exclude_recent_dois(doi_list):
    '''
    For arriving at a list of DOIs ostensibly missing from PMC, remove the most recent articles
    which likely have not yet had the opportunity to propagate.
    :return: a list of missing DOIs which are old enough to be expected to be on PMC.
    '''
    missing_pmc_articles = []
    for doi in doi_list:
        article_file = doi_to_file(doi)
        if compare_article_pubdate(article_file):
            missing_pmc_articles.append(doi)
    return missing_pmc_articles


def check_if_doi_resolves(doi, plos_valid=True):
    """
    Return metadata for a given DOI. If the link works, make sure that it points to the same DOI
    Checks first if it's a valid DOI
    or see if it's a redirect.
    """
    if plos_valid and validate_doi(doi) is False:
        return "Not valid PLOS DOI structure"
    url = "http://dx.doi.org/" + doi
    if check_if_link_works(url):
        headers = {"accept": "application/vnd.citationstyles.csl+json"}
        r = requests.get(url, headers=headers)
        r_doi = r.json()['DOI']
        if r_doi == doi:
            return 'works'
        else:
            return r_doi
    else:
        return "doesn't work"


def process_missing_plos_articles(plos_articles=None, pmc_articles=None):
    '''
    For sets of PLOS's corpus from PMC and PLOS, see which article are missing from PLOS's version
    of the Corpus by removing Currents articles, checking if articles are live on journals.plos.org,
    and checking that the DOIs resolve. Prints the different kinds of errors that can occur.
    :return: list of missing articles
    '''
    if plos_articles is None or not plos_articles:
        plos_articles = get_all_plos_dois()
    if pmc_articles is None or not pmc_articles:
        doi_to_pmc = get_articles_by_doi_field(check_new=False)
        pmc_articles = list(doi_to_pmc.keys())
    missing_plos_articles = list(set(pmc_articles) - set(plos_articles))

    # remove Currents articles
    for article in list(missing_plos_articles):
        if article.startswith('10.1371/currents') or \
             len(article) == 21 or \
             article == '10.1371/198d344bc40a75f927c9bc5024279815':
            missing_plos_articles.remove(article)

    # check if articles are live on journals.plos.org
    # check if DOIs resolve
    missing_articles_link_works = []
    missing_articles_404_error = []
    doi_works = []
    doi_doesnt_work = []
    doi_mismatch = []
    doi_has_space = []
    for doi in missing_plos_articles:
        if ' ' in doi:
            doi_has_space.append(doi)
            continue
        doi_check = check_if_doi_resolves(doi)
        if doi_check == 'works':
            doi_works.append(doi)
        elif doi_check == "doesn't work":
            doi_doesnt_work.append(doi)
        else:
            doi_mismatch.append(doi)
            continue
        url = doi_to_url(doi)
        article_exists = check_if_link_works(url)
        if article_exists:
            missing_articles_link_works.append(doi)
        else:
            missing_articles_404_error.append(doi)

    doi_mismatch = sorted(doi_mismatch)
    link404_invalid_doi = sorted(list(set(missing_articles_404_error).intersection(doi_doesnt_work)))
    linkworks_valid_doi = sorted(list(set(missing_articles_link_works).intersection(doi_works)))

    if doi_has_space:
        print('\033[1m' + 'PMC DOI fields with spaces in them:')
        for doi in doi_has_space:
            print('\033[0m' + '"' + doi + '" \n')
    if linkworks_valid_doi:
        print('\033[1m' + 'Working articles that need to be re-indexed on Solr:')
        print('\033[0m' + '\n'.join(linkworks_valid_doi), '\n')
    if link404_invalid_doi:
        print('\033[1m' + 'Articles on PMC but not on solr or journals:')
        print('\033[0m' + '\n'.join(missing_articles_404_error), '\n')
    if doi_mismatch:
        print('\033[1m' + 'Missing PLOS articles where DOI resolves to different DOI:')
        for doi in doi_mismatch:
            print('\033[0m', doi, 'resolves to:', check_if_doi_resolves(doi))

    remainder = list(set(missing_plos_articles) - set(linkworks_valid_doi + missing_articles_404_error +
                     doi_mismatch + doi_has_space))
    if remainder:
        print('\n \033[1m' + "Other articles on PMC that aren't working correctly for PLOS:")
        print('\033[0m' + '\n'.join(remainder), '\n')
    return missing_plos_articles


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
        local_articles = [file_to_doi(article_file) for article_file in listdir_nohidden(corpusdir)]
    missing_local_articles = set(solr_articles) - set(local_articles)
    if missing_local_articles:
        print('re-run plos_corpus.py to download latest {} PLOS articles locally.'.format(len(missing_local_articles)))
    missing_solr_articles = list(set(local_articles) - set(solr_articles))
    plos_articles = set(solr_articles + local_articles)
    if missing_solr_articles:
        print('\033[1m' + 'Articles that needs to be re-indexed on Solr:')
        print('\033[0m' + '\n'.join(sorted(missing_solr_articles)))

    return plos_articles


def get_random_list_of_dois(directory=corpusdir, count=100):
    '''
    :return: a list of random DOI articles for analysis
    '''
    article_list = listdir_nohidden(directory)
    np_list = np.array(article_list)
    sample_file_list = list(np.random.choice(np_list, size=count, replace=False))
    sample_doi_list = [file_to_doi(file) for file in sample_file_list]
    return sample_doi_list


def process_missing_pmc_articles(pmc_articles=None, plos_articles=None):
    '''
    For sets of PLOS's corpus from PMC and PLOS, see which article are missing from PMC's version
    of the Corpus by updating the PMCID:DOI mapping document, removing articles too recent to be indexed
    (pubdate less than 3 weeks ago), and excluding uncorrected proofs.
    :return: list of missing articles from PMC
    '''
    if pmc_articles is None:
        doi_to_pmc = get_articles_by_doi_field(check_new=False)
        pmc_articles = list(doi_to_pmc.keys())

    if plos_articles is None:
        plos_articles = get_all_plos_dois()
    missing_pmc_dois = list(set(plos_articles) - set(pmc_articles))

    # Query for PMC updates & update DOI-to-PMCID dictionary
    if missing_pmc_dois:
        full_pmc_dict, dois_not_in_pmc = update_pmc_dict_by_doi(missing_pmc_dois)

    # Exclude PLOS Medicine quizzes
    for doi in dois_not_in_pmc:
        if "pmed" in doi:
            article = doi_to_article(doi)
            article_type = get_plos_article_type(article)
            if article_type == 'Quiz':
                dois_not_in_pmc.remove(doi)

    # Remove articles too recent to have been indexed on PMC
    if dois_not_in_pmc:
        missing_pmc_dois = exclude_recent_dois(dois_not_in_pmc)

    # Remove uncorrected proofs
    if missing_pmc_dois:
        for doi in missing_pmc_dois:
            article_file = doi_to_file(doi)
            if check_if_uncorrected_proof(article_file):
                missing_pmc_dois.remove(doi)

    # Make sure that the DOI resolves
    for doi in missing_pmc_dois:
        resolves = check_if_doi_resolves(doi)
        if resolves != "works":
            print('DOI not working for this PLOS DOI:', doi, resolves)
            missing_pmc_dois.remove(doi)

    if len(missing_pmc_dois) == 0:
        print('No PMC articles missing.')
    else:
        for doi in missing_pmc_dois:
            if ' ' in doi:
                print('There is a space in this DOI: ' + '"' + doi + '"')
        print('\033[1m' + 'Articles missing from PMC:')
        print('\033[0m' + '\n'.join(sorted(missing_pmc_dois)), '\n')

    return missing_pmc_dois


def get_all_pmc_dois(retstart=0, retmax=80000, count=None):
    """
    Query the entrez database to get a comprehensive list of all PMCIDs associated with all PLOS journals,
    individually included in the search url.
    See https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch for more info on search parameters
    :return: the full list of PMCIDs in PMC for PLOS articles
    """
    pmc_allplos_query_url = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term='
                             '((((((((("PLoS+ONE"[Journal])+OR+"PLoS+Genetics"[Journal])+OR+"PLoS+Pathogens"[Journal])'
                             'OR+"PLoS+Neglected+Tropical+Diseases"[Journal])+OR+"PLoS+Computational+Biology"[Journal])'
                             'OR+"PLoS+Biology"[Journal])+OR+"PLoS+Medicine"[Journal])+OR+"plos+currents"[Journal])+OR+'
                             '"PLoS Clinical Trials"[Journal])'
                             '&retmode=json&tool=corpustest&email={0}'.format(USER_EMAIL))

    pmcidlist = []
    r = requests.get(pmc_allplos_query_url).json()
    if count is None:
        count = int(r['esearchresult']['count'])
        print(count, "articles found in PMC")
    while retstart < count:
        query = pmc_allplos_query_url + '&retstart={0}&retmax={1}'.format(retstart, retmax)
        r = requests.get(query).json()
        idlist = r['esearchresult']['idlist']
        for id in idlist:
            pmcidlist.append('PMC' + id)
        retstart += retmax
        time.sleep(1)
    pmcidlist = sorted(list(set(pmcidlist)))
    if pmcidlist != count:
        print("Error in number of IDs returned. Got {} when expected {}.".format(len(pmcidlist), count))

    return pmcidlist


def update_local_pmc_from_remote():
    '''
    Using the current set of articles indexed live on PMC, compare them to the locally maintained index.
    If any of them are missing, download them to the local .csv dictionary.
    :return: full dictionary of PMC IDs'''
    remote_pmc_ids = get_all_pmc_dois()
    local_pmc_dict = get_articles_by_doi_field()
    local_pmc_ids = list(local_pmc_dict.values())
    missing_pmcids = list(set(remote_pmc_ids) - set(local_pmc_ids))
    if missing_pmcids:
        full_pmc_dict, dois_not_in_pmc = update_pmc_dict_by_doi(missing_pmcids)
    else:
        full_pmc_dict = doi_to_pmc
    weird_pmc_ids = list(set(local_pmc_ids) - set(remote_pmc_ids))
    if 0 < weird_pmc_ids < 10000:
        print("Some articles on local not on remote:", print(weird_pmc_ids))
    return full_pmc_dict


def get_needed_pmc_articles():
    """
    Compare local to remote set of PLOS PMC IDs.
    TO DO: Add check for latest update date
    :return: tuple of doi dict, and list of DOIs that are on remote and not local, to be downloaded.
    """
    doi_to_pmc = get_articles_by_doi_field(check_new=False)
    remote_pmc_ids = list(doi_to_pmc.values())
    local_pmc_ids = extract_filenames(pmcdir, extension='.nxml')
    missing_pmc_articles = list(set(remote_pmc_ids) - set(local_pmc_ids))
    return doi_to_pmc, missing_pmc_articles


def get_pmc_article_zip_links():
    """
    Creates a dictionary mapping every PMC ID to the partial PMC download URL
    Based on txt file hosted by PMC
    TO DO: see if there's a way to download monthly, weekly, etc from PMC
    :return: dictionary mapping PMC IDs to partial download links
    """

    # write info file to disk if it doesn't exist already or is too old
    try:
        mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(pmc_file_list))
        file_age = datetime.datetime.now() - mod_date
        if file_age > datetime.timedelta(days=1):
            os.remove(pmc_file_list)
    except FileNotFoundError:
        pass
    if os.path.isfile(pmc_file_list) is False:
        with open(pmc_file_list, 'w') as f:
            f.write(requests.get('http://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.txt').text)

    # parse file by line
    with open(pmc_file_list) as f:
        pmc_lists = [x.strip().split('\t') for x in f]

    # turn into dictionary mapping of PMCID to partial PMC URL
    pmc_urls = {d[2]: d[0] for d in pmc_lists[1:]}

    return pmc_urls


def download_pmc_article_xml(missing_pmc_articles=None, pmc_urls=None):
    """
    Get missing PMC articles. Get dictionary mapping them to partial URLs. Download and unzip the tarballs.
    Keep and rename the nxml files and delete the others.
    NOTE: This hasn't worked very well. PMC connections are unreliable & there are a lot of timeouts.
    :return: list of files downloaded from PMC
    """
    new_pmc_articles = []
    if missing_pmc_articles is None:
        doi_to_pmc, missing_pmc_articles = get_needed_pmc_articles()
        print(len(missing_pmc_articles), "PMC articles to download.")
    if missing_pmc_articles:
        if pmc_urls is None:
            pmc_urls = get_pmc_article_zip_links()
        # download and unzip tarballs
        for article in missing_pmc_articles:
            dl_url = PMC_FTP_URL + pmc_urls[article]
            filename = (pmc_urls[article]).split("/")[3]
            local_file = os.path.join(newpmcarticledir, filename)
            if os.path.isfile(local_file) is False:
                try:
                    download(dl_url, local_file)
                    unzip_articles(directory=newpmcarticledir, filetype='tar', file=filename)
                except RuntimeError:
                    print('Error downloading', article)
                    continue

        # get rid of non-.nxml files
        allfiles = glob.glob('New_PMC_articles/*/*')
        for file in allfiles:
            if file.endswith('.nxml') is False:
                os.remove(file)

        # move and process the nxml files
        files = glob.glob('New_PMC_articles/*/*')
        for old_file in files:
            # make sure directory and linked doi line up
            directory = (old_file).split('/')[1]
            linked_doi = doi_to_pmc[get_article_doi(article_file=old_file)]
            if linked_doi == directory:
                # rename file from directory & move to higher level directory
                new_file = '/'.join(((old_file).split('/'))[0:2]) + '.nxml'
                shutil.move(old_file, new_file)
                new_pmc_articles.append(new_file)
            else:
                print('error:', linked_doi, directory)
        for directory in glob.glob('New_PMC_articles/*/'):
            os.rmdir(directory)

    return new_pmc_articles


def move_pmc_articles(source, destination):
    """
    Move PMC articles from one folder to another
    :param source: Temporary directory of new article files
    :param destination: Directory where files are copied to
    """
    oldnum_destination = len(listdir_nohidden(destination, extension='.nxml'))
    oldnum_source = len(listdir_nohidden(source, extension='.nxml'))
    if oldnum_source > 0:
        print("PMC Corpus started with",
              oldnum_destination,
              "articles.\nFile moving procedure initiated, please hold...")
        copytree(source, destination, ignore=ignore_func)
        newnum_destination = len(listdir_nohidden(destination))
        if newnum_destination - oldnum_destination > 0:
            print(newnum_destination - oldnum_destination,
                  "files moved. PMC Corpus now has",
                  newnum_destination, "articles.")
            logging.info("New article files moved successfully")
    else:
        print("No files found to move in source directory.")
        logging.info("No article files moved")
    # Delete temporary folder in most cases
    if source == newarticledir:
        shutil.rmtree(source)
