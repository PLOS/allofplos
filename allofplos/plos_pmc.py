""" Small stand-alone script for getting all the PMC IDs for PLOS articles.
"""

import requests
import time
from plos_corpus import *
from samples.corpus_analysis import *

newpmcarticledir = "new_pmc_articles"
pmc_csv = 'doi_to_pmc.csv'
pmcdir = "pmc_articles/"
# xml URL takes PMC identifier minus 'PMC'
pmc_xml_url = 'https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:'
pmc_xml_url_suffix = '&metadataPrefix=pmc'

# can query up to 200 DOIs from PMC
USER_EMAIL = 'elizabeth.seiver@gmail.com'
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
newpmcarticledir = "new_pmc_articles"
max_invalid_files_to_print = 100

def get_all_pmc_dois(retstart=0, retmax=80000, count=None):
    """Query the entrez database to get a comprehensive list of all PMCIDs associated with all PLOS journals,
    individually included in the search url.
    Supposedly can return 100,000, but based on the maximum not working for another function, lowered to 80K to be safe.
    :param restart: the first record to return
    :param retmax: the maximum number of records to return
    :return: the full list of PMCIDs in PMC for PLOS articles
    """
    pmc_allplos_query_url = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&term='
                             '(((((("PLoS+ONE"[Journal])+OR+"PLoS+Genetics"[Journal])+OR+"PLoS+Pathogens"[Journal])'
                             'OR+"PLoS+Neglected+Tropical+Diseases"[Journal])+OR+"PLoS+Computational+Biology"[Journal])'
                             'OR+"PLoS+Biology"[Journal])+OR+"PLoS+Medicine"[Journal]+OR+"plos+currents"[Journal]'
                             '&retmode=json&tool=corpustest&email=email@provider.com')

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

    print(len(pmcidlist), "articles found")
    return pmcidlist


def get_pmc_doi_dict(doi_list, chunk_size=150):
    '''Using the PMC ID query API, return the accompanying PMCID for each DOI in a given list.
    Can (ostensibly) query up to 200 DOIs at a time but sometimes that doesn't work.
    :param doi list: a list of valid PLOS DOIs
    :param chunk_size: number of DOIs to query at a single time
    :return: tuple of dictionary mapping DOI to PMCID, list of DOIs not found in PMC
    '''
    
    doi_to_pmc = {}
    dois_not_in_pmc = []
    # Make chunks of 200 DOIs at a time
    list_chunks = [doi_list[x:x+chunk_size] for x in range(0, len(doi_list), chunk_size)]
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


def get_pmc_articles():
    """
    :return: a list of all article files in PMC folder
    """
    # step 1: download tarball file if needed
    pmc_url = 'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/articles.O-Z.xml.tar.gz'
    pmcdir = 'pmc_articles/'
    pmc_local_tar = 'pmc_files.tar.gz'
    pmc_path = os.path.join(pmcdir, pmc_local_tar)
    if os.path.isdir(pmcdir) is False:
        os.mkdir(pmcdir)
        print('Creating folder for PMC article xml')

    if len([name for name in os.listdir(pmcdir) if os.path.isfile(os.path.join(pmcdir, name))]) < 200000:
        print('Not enough articles in pmcdir, re-downloading zip file')
        path = download(pmc_url, pmc_path)

        # Step 2: unzip archive
        unzip_articles(file_path=pmc_path, extract_directory=pmcdir, filetype='tar')

        # Step 3: delete non-PLOS folders
        listdirs = glob("pmc_articles/*/")
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
    for article in missing_plos_articles:
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

    remainder = set(missing_plos_articles) - set(linkworks_valid_doi + missing_articles_404_error +
                     doi_mismatch + doi_has_space)
    if remainder:
        print('\n \033[1m' + "Other articles on PMC that aren't working correctly for PLOS:")
        print('\033[0m' + '\n'.join(remainder), '\n')
    return missing_plos_articles



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
        print("Error in number of IDs returned. Got {0} when expected {1}."
              .format(len(pmcidlist), count))

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
        allfiles = glob.glob('new_pmc_articles/*/*')
        for file in allfiles:
            if file.endswith('.nxml') is False:
                os.remove(file)

        # move and process the nxml files
        files = glob.glob('new_pmc_articles/*/*')
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
        for directory in glob.glob('new_pmc_articles/*/'):
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


if __name__ == '__main__':
    pmcidlist = get_all_pmc_dois()
