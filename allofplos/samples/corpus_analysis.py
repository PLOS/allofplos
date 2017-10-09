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
import os
import progressbar
import random
import requests


from plos_corpus import (listdir_nohidden, check_article_type, get_article_xml, uncorrected_proofs_text_list,
                         get_related_article_doi, download_updated_xml, get_all_solr_dois, doi_to_file,
                         file_to_doi, newarticledir, get_article_pubdate, doi_to_url, download_check_and_move)
from plos_regex import (full_doi_regex_match, validate_doi, validate_file, validate_url, currents_doi_filter)

counter = collections.Counter
corpusdir = 'allofplos_xml'
max_invalid_files_to_print = 100
pmcdir = 'pmc_articles'


def validate_corpus(corpusdir=corpusdir):
    """
    For every local article file and DOI listed on Solr, validate file names, DOIs, URLs in terms of
    regular expressions.
    Stops checking as soon as encounters problem and prints it
    :return: boolean of whether corpus passed validity checks
    """
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
    plos_files = listdir_nohidden(corpusdir)
    if plos_files:
        plos_valid_filenames = [article for article in plos_files if validate_file(article)]
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
    article_categories = get_article_xml(article_file=article_file,
                                         tag_path_elements=["/",
                                                            "article",
                                                            "front",
                                                            "article-meta",
                                                            "article-categories"])
    subject_list = article_categories[0].getchildren()

    for i, subject in enumerate(subject_list):
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
        dtd = get_article_xml(article_file=article_file,
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
    max_value = len(article_list)
    bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
    for i, article_file in enumerate(article_list):
        updated = download_updated_xml(article_file=article_file)
        if updated:
            articles_different_list.append(article_file)
        if list_provided:
            article_list.remove(article_file)  # helps save time if need to restart process
        bar.update(i+1)
    bar.finish()
    print(len(article_list), "article checked for updates.")
    print(len(articles_different_list), "articles have updates.")
    return articles_different_list


# These functions are for getting & analyzing the PLOS Corpus from PMC


def get_article_doi(article_file):
    raw_xml = get_article_xml(article_file=article_file,
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


def check_solr_doi(doi):
    '''
    For an article doi, see if there's a record of it in Solr.
    '''
    solr_url = 'http://api.plos.org/search?q=*%3A*&fq=doc_type%3Afull&fl=id,&wt=json&indent=true&fq=id:%22{}%22'.format(doi)
    article_search = requests.get(solr_url).json()
    return bool(article_search['response']['numFound'])


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
        print('re-run plos_corpus.py to download latest {0} PLOS articles locally.'
              .format(len(missing_local_articles)))
    missing_solr_articles = set(local_articles) - set(solr_articles)
    plos_articles = set(solr_articles + local_articles)
    if missing_solr_articles:
        print('\033[1m' + 'Articles that needs to be re-indexed on Solr:')
        print('\033[0m' + '\n'.join(sorted(missing_solr_articles)))

    return plos_articles


def get_random_list_of_dois(directory=corpusdir, count=100):
    '''
    Gets a list of random DOIs. Tries first to construct from local files in
    corpusdir, otherwise tries Solr DOI list as backup.
    :param directory: defaults to searching corpusdir
    :param count: specify how many DOIs are to be returned
    :return: a list of random DOIs for analysis
    '''
    try:
        article_list = listdir_nohidden(directory)
        sample_file_list = random.sample(article_list, count)
        sample_doi_list = [file_to_doi(file) for file in sample_file_list]
    except OSError:
        doi_list = get_all_solr_dois()
        sample_doi_list = random.sample(doi_list, count)
    return sample_doi_list


def get_plos_journal(article_file, caps_fixed=True):
    """
    For an individual PLOS article, get the journal it was published in.
    :param article_file: individual local PLOS XML article
    :param caps_fixed: whether to render the journal name correctly or as-is
    :return: PLOS journal at specified xpath location
    """
    try:
        journal = get_article_xml(article_file=article_file,
                                  tag_path_elements=["/",
                                                     "article",
                                                     "front",
                                                     "journal-meta",
                                                     "journal-title-group",
                                                     "journal-title"])
        journal = journal[0].text
    except IndexError:
        journal_meta = get_article_xml(article_file='allofplos_xml/journal.pone.0047704.xml',
                                       tag_path_elements=["/",
                                                          "article",
                                                          "front",
                                                          "journal-meta"])
        for journal_child in journal_meta[0]:
            if journal_child.attrib['journal-id-type'] == 'nlm-ta':
                journal = journal_child.text
                break

    if caps_fixed:
        journal = journal.split()
        if journal[0].lower() == 'plos':
            journal[0] = "PLOS"
        journal = (' ').join(journal)
    return journal


def get_article_title(article_file):
    """
    For an individual PLOS article, get its title.
    :param article_file: individual local PLOS XML article
    :return: string of article title at specified xpath location
    """
    title = get_article_xml(article_file=article_file,
                            tag_path_elements=["/",
                                               "article",
                                               "front",
                                               "article-meta",
                                               "title-group",
                                               "article-title"])
    title_text = et.tostring(title[0], encoding='unicode', method='text')
    return title_text


def parse_article_date(date_element, date_format='%d %m %Y'):
    """
    For an article date element, convert XML to a datetime object
    :param date_format: string format used to convert to datetime object
    :return: datetime object
    """
    day = ''
    month = ''
    year = ''
    for item in date_element.getchildren():
        if item.tag == 'day':
            day = item.text
        if item.tag == 'month':
            month = item.text
        if item.tag == 'year':
            year = item.text
    if day:
        date = (day, month, year)
        string_date = ' '.join(date)
        date = datetime.datetime.strptime(string_date, date_format)
    elif month:
        # try both numerical & word versions of month
        date = (month, year)
        string_date = ' '.join(date)
        try:
            date = datetime.datetime.strptime(string_date, '%m %Y')
        except ValueError:
            date = datetime.datetime.strptime(string_date, '%B %Y')
    elif year:
        date = year
        date = datetime.datetime.strptime(date, '%Y')
    else:
        print('date error')
        date = ''
    return date


def get_article_abstract(article_file):
    """
    For an individual article in the PLOS corpus, create a tuple of a set of metadata fields sbout that corpus.
    Make it small, medium, or large depending on number of fields desired.
    :param article_file: individual local PLOS XML article
    :return: plain-text string of content in abstract
    """
    abstract = get_article_xml(article_file, tag_path_elements=["/",
                                                                "article",
                                                                "front",
                                                                "article-meta",
                                                                "abstract"])
    try:
        abstract_text = et.tostring(abstract[0], encoding='unicode', method='text')
    except IndexError:
        if check_article_type(article_file) == 'research-article' and \
          get_plos_article_type(article_file) == 'Research Article':
            print('No abstract found for research article {}'.format(file_to_doi(article_file)))

        abstract_text = ''

    # clean up text: rem white space, new line marks
    abstract_text.replace('  ', '').strip()
    # if '\n' in abstract_text:
    #     print(abstract_text.decode('utf-8'))

    return abstract_text


def get_article_dates(article_file, string=False):
    """
    For an individual article, get all of its dates
    :param article_file: file path/DOI of the article
    :return: dictionary of date types mapped to datetime objects for that article
    """
    dates = {}

    tag_path_1 = ["/",
                  "article",
                  "front",
                  "article-meta",
                  "pub-date"]
    raw_xml_1 = get_article_xml(article_file=article_file,
                                tag_path_elements=tag_path_1)
    for element in raw_xml_1:
        pub_type = element.get('pub-type')
        date = parse_article_date(element)
        dates[pub_type] = date

    tag_path_2 = ["/",
                  "article",
                  "front",
                  "article-meta",
                  "history"]
    raw_xml_2 = get_article_xml(article_file=article_file,
                                tag_path_elements=tag_path_2)
    for element in raw_xml_2:
        for part in element:
            date_type = part.get('date-type')
            date = parse_article_date(part)
            dates[date_type] = date
    if 'received' in dates and 'accepted' in dates:
        if not dates['received'] <= dates['accepted'] <= dates['epub']:
            print('{} dates not in correct order: {}'.format(article_file, dates))
    if string:
        for key, value in dates.items():
            dates[key] = value.strftime('%Y-%m-%d')

    return dates


def get_article_counts(article_file):
    """
    For a single article, return a dictionary of the several counts functions that are available
    (figures: fig-count, pages: page-count, tables: table-count)
    :param article_file: file path/DOI of the article
    :return: counts dictionary
    """
    counts = {}

    tag_path = ["/",
                "article",
                "front",
                "article-meta",
                "counts"]
    raw_xml = get_article_xml(article_file=article_file,
                              tag_path_elements=tag_path)
    for element in raw_xml:
        for count_item in element:
            count = count_item.get('count')
            count_type = count_item.tag
            counts[count_type] = count
    if len(counts) > 3:
        print(counts)
    return counts


def get_article_body_word_count(article_file):
    """
    For an article, get how many words are in the body
    :param article_file: individual local PLOS XML article
    :return: count of words in the body of the PLOS article
    """
    body = get_article_xml(article_file, tag_path_elements=["/",
                                                            "article",
                                                            "body"])
    try:
        body_text = et.tostring(body[0], encoding='unicode', method='text')
        body_word_count = len(body_text.split(" "))
    except IndexError:
        print("Error parsing article body: {}".format(article_file))
        body_word_count = 0
    return body_word_count


def get_article_metadata(article_file, size='small'):
    """
    For an individual article in the PLOS corpus, create a tuple of a set of metadata fields sbout that corpus.
    Make it small, medium, or large depending on number of fields desired.
    :param article_file: individual local PLOS XML article
    :param size: small, medium or large, aka how many fields to return for each article
    :return: tuple of metadata fields
    """
    doi = file_to_doi(article_file)
    filename = os.path.basename(doi_to_file(article_file)).rstrip('.xml')
    title = get_article_title(article_file)
    journal = get_plos_journal(article_file)
    jats_article_type = check_article_type(article_file)
    plos_article_type = get_plos_article_type(article_file)
    dtd_version = get_article_dtd(article_file)
    dates = get_article_dates(article_file, string=True)
    (pubdate, collection, received, accepted) = ('', '', '', '')
    pubdate = dates['epub']
    counts = get_article_counts(article_file)
    (fig_count, table_count, page_count) = ('', '', '')
    body_word_count = get_article_body_word_count(article_file)
    abstract = get_article_abstract(article_file)
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
    metadata = [doi, filename, title, journal, jats_article_type, plos_article_type, dtd_version, pubdate,
                received, accepted, collection, fig_count, table_count, page_count, body_word_count, abstract]
    metadata = tuple(metadata)
    if len(metadata) == 16:
        return metadata
    else:
        print('Error in {}: {} items'.format(article_file, len(metadata)))
        return False


def get_corpus_metadata(article_list=None):
    """
    Run get_article_metadata() on a list of files, by default every file in corpusdir
    Includes a progress bar
    :param article_list: list of articles to run it on
    :return: list of tuples for each article
    """
    if article_list is None:
        article_list = listdir_nohidden(corpusdir)
    max_value = len(article_list)
    bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
    corpus_metadata = []
    for i, article_file in enumerate(article_list):
        metadata = get_article_metadata(article_file)
        corpus_metadata.append(metadata)
        bar.update(i+1)
    bar.finish()
    return corpus_metadata


def corpus_metadata_to_csv(corpus_metadata=None, csv_file='allofplos_metadata.csv'):
    """
    Convert list of tuples from get_article_metadata to csv
    :param corpus_metadata: the list of tuples, defaults to creating from corpusdir
    :return: None
    """
    if corpus_metadata is None:
        corpus_metadata = get_corpus_metadata()
    with open(csv_file, 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(['doi', 'filename', 'title', 'journal', 'jats_article_type', 'plos_article_type',
                          'dtd_version', 'pubdate', 'received', 'accepted', 'collection', 'fig_count', 'table_count',
                          'page_count', 'body_word_count', 'abstract'])
        for row in corpus_metadata:
            csv_out.writerow(row)


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


def update_corpus_metadata_csv(csv_file='allofplos_metadata.csv', comparison_dois=None):
    """
    Incrementally update the metadata of PLOS articles in the csv file
    :param csv_file: csv file of data, defaults to 'allofplos_metadata.csv'
    :comparison_dois: list of DOIs to check whether their metadats is included
    return updated corpus metadata
    """
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
    local_doi_list = [file_to_doi(article_file) for article_file in listdir_nohidden(corpusdir)]
    files_needed_list = list(set(dois_needed_list) - set(local_doi_list))
    if files_needed_list:
        print('Local corpus must be updated before .csv metadata can be updated.\nUpdating local corpus now')
        download_check_and_move(files_needed_list,
                                uncorrected_proofs_text_list,
                                tempdir=newarticledir,
                                destination=corpusdir)

    # Step 4: append new data to existing list
    new_corpus_metadata = get_corpus_metadata(article_list=dois_needed_list)
    corpus_metadata.extend(new_corpus_metadata)
    # Step 5: write new dataset to .csv
    corpus_metadata_to_csv(corpus_metadata=corpus_metadata, csv_file=csv_file)
    return corpus_metadata
