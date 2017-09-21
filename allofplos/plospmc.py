""" Small stand-alone script for getting all the PMC IDs for PLOS articles.
"""

import requests
import time

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

if __name__ == '__main__':
    pmcidlist = get_all_pmc_dois()
