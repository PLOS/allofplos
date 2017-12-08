# Copyright (c) 2014 Public Library of Science

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# !/usr/bin/env python
#
# Code written by Adam Becker
# Code refactored into Python 3 by Elizabeth Seiver


"""
citation_utilities.py
Version 0.10, 2014-01-24
"""


from numpy import median
from bs4 import BeautifulSoup
from itertools import chain, compress
import requests
from urllib.parse import quote
import json
import re
from multiprocessing import Pool

from tqdm import tqdm


def soupify(filename):
    '''Opens the given XML file, parses it using Beautiful Soup, and returns the output.'''
    f = open(filename, "r")
    soup = BeautifulSoup(f, features="xml")
    f.close()
    return soup


def remote_retrieve(doi, filename=''):
    '''Given the DOI of a PLOS paper, downloads the XML.'''
    # First, see if the file was already downloaded.
    if filename:
        try:
            open(filename)
            return filename
        except IOError:
            pass
    headers = {"Content-Type": "application/xml"}
    r = requests.get("http://www.plosone.org/article/fetchObjectAttachment.action?uri=info:doi/" + doi + "&representation=XML", headers=headers)
    # Doesn't matter whether it's a PLOS ONE article or not -- this will work for any article in any PLOS journal.
    r.encoding = "UTF-8"  # This is needed to keep the encoding on the papers correct.
    if filename:
        f = open(filename, "w")
        f.write(r.text.encode("UTF-8"))
        f.close()
        return filename
    # Nothing after a return statement is executed, so the following line will only happen if filename is False.
    return r.text


def remote_soupify(doi):
    '''Given the DOI of a PLOS paper, downloads the XML and parses it using Beautiful Soup.'''
    headers = {"Content-Type": "application/xml"}
    r = requests.get("http://www.plosone.org/article/fetchObjectAttachment.action?uri=info:doi/" + doi + "&representation=XML", headers=headers)
    # Doesn't matter whether it's a PLOS ONE article or not -- this will work for any article in any PLOS journal.
    r.encoding = "UTF-8"  # This is needed to keep the encoding on the papers correct.
    soup = BeautifulSoup(r.text, features="xml")
    return soup


def citation_grouper(paper):
    '''
    Don't call this directly -- use one of the dictionary or database functions instead.
    Given a soupified XML paper, returns a list of the 'citation groups' within that paper.
    A citation group is all of the papers that are cited together at a certain point in the paper -- the bare stuff of inline co-citations.
    So, for example, a citation group might simply be [1], or it could be [2]-[10], or even [11], [13]-[17], [21].
    The elements within the returned list are themselves lists of soupified XML elements corresponding to citations and connectives.
    '''

    # Make a place for the output to live.
    groups = []

    # Find the first citation.
    cite = paper.find(attrs={"ref-type":"bibr"})

    # This is the loop that actually goes through and finds the inline co-citation groups.
    # It'll continue as long as the "cite" variable isn't None, False, or 0.
    while cite:
        # Make a place for the citation group to live, and add the first member of the group.
        group = [cite]

        # Get the next sibling on the XML tree,
        # determine whether it's part of the group or not,
        # rinse & repeat.
        next = cite.next_sibling
        while next and ((next.name == "xref" and next["ref-type"] == "bibr") or ((next == ", " or next == "," or next == "\u2013" or next == "-" or next == "\u2014" or next == " ") and (next.next_sibling and next.next_sibling.name == "xref" and next.next_sibling["ref-type"] == "bibr"))):
            group.append(next)
            next = next.next_sibling

        # Put the group into the list of groups, then find the next citation.
        groups.append(group)
        try:
            cite = next.find_next(attrs={"ref-type": "bibr"})  # At the end of the document, this will return None, breaking the loop condition.
        except AttributeError:
            cite = cite.find_next(attrs={"ref-type": "bibr"})
            # we need this try-except clause in the event that the citation has no further siblings, meaning next will be None and will fail to have the find_next method.

    return groups


def number(citation):
    '''A little function that translates XML citations into their citation numbers.'''
    # I attempted to make this function more subtle and capable of handling a wider variety of citation styles.
    # I failed! But the attempt is instructive, so it's commented out below.
    #
    # try:
    #     # Sometimes, the citation tag is inside the brackets, eg. [<xref>12</xref>]
    #     naive = int(citation.text)
    #     return naive
    # except ValueError:
    #     try:
    #         # But sometimes, the brackets are inside the tag.
    #         less_naive = int(citation.text[1:-1])
    #         return less_naive
    #     except ValueError:
    #         # And sometimes, there's a full-text citation rather than a number! (Only on older papers, I think.)
    #         rid = citation["rid"]
    #         ref = citation.find_next("ref", attrs = {"id": rid})
    #         label = ref.label
    #         # number = re.search(r"\d+", citation.text)
    #         number = re.search(r"\d+", label.text)
    #         return int(number.group())
    #
    # The real function is below.
    # This just pulls the reference ID off of the citation's XML tags,
    # then looks up the reference number of that RID down in the references section of the paper.
    rid = citation["rid"]
    ref = citation.find_next("ref", attrs={"id": rid})
    label = ref.label
    try:
        number = re.search(r"\d+", label.text)
        return int(number.group())
    except AttributeError:
        print("Missing reference labels on DOI " + ref.find_previous("article-id", attrs={"pub-id-type": "doi"}).text.encode("UTF-8") + " for reference " + citation.text.encode("UTF-8") + ".")
        return 0  # This should be a reasonable thing to return in the case that no citation number is found: it won't cause errors elsewhere, but it's easy to track.


def group_cleaner(group):
    '''
    Don't call this directly -- use one of the dictionary or database functions instead.
    Given a citation group like the ones in the list returned by citation_grouper,
    returns lists of integers that correspond to citation numbers.
    So XML corresponding to [3], [5]-[7] would be returned as [3, 5, 6, 7].
    '''
    # The idea here relies (as it almost has to)
    # on the fact that the citation groups have citations alternating with punctuation
    # (that, or they're just a single citation).
    # So we start with a citation, then punctuation, then citation, and so on,
    # always starting and ending with a citation -- and sometimes that's the same one, the only member of the group.

    # Make a place for the output to live.
    cite_numbers = []

    # Get the first element
    first_citation = group[0]
    old_number = number(first_citation)
    cite_numbers.append(old_number)
    # Set up the loop.
    hyphen_bool = False

    for thing in group[1:]:
        if thing.name == "xref":
            new_number = number(thing)
            if hyphen_bool:
                cite_numbers.extend(list(range(old_number + 1, new_number)))
            cite_numbers.append(new_number)
            old_number = new_number
        else:
            # Figure out whether the punctuation is a hyphen or a comma, and act accordingly.
            if thing == "\u2013" or thing == "-" or thing == "\u2014":
                hyphen_bool = True
            else:
                hyphen_bool = False

    return cite_numbers


def doi(number, paper, verbose=True):
    '''
    DEPRECATED in favor of doi_batch.
    Given a soupified paper and a citation number, attempts to return the DOI of the reference
    by searching the text of the reference and doing a CrossRef search if that fails.
    Returns None if no DOI can be found.
    Verbose does what it sounds like.
    NB: The automated CrossRef search has intermittent trouble finding things.
    Not sure why, but this function definitely fails to find DOIs that are nonetheless in the CrossRef database.
    '''
    # Get the references.
    references = paper.find("ref-list")
    ref_label = references.find("label", text=str(number))
    ref = ref_label.find_next_sibling("mixed-citation").text
    # Try searching for an inline DOI first.
    doimatch = re.search(r"\sdoi:|\sDOI:|\sDoi:|\.doi\.|\.DOI\.", ref)
    if doimatch:
        rawdoi = ref[doimatch.start():]
        doi = rawdoi[rawdoi.index("10."):]  # all DOI's start with 10., see reference here: http://www.doi.org/doi_handbook/2_Numbering.html#2.2

        # Removing whitespace and anything afterwards.
        space = re.search(r"\s", doi)
        if space:
            doi = doi[:space.start()]

        # Removing trailing periods.
        if doi[-1] == ".":
            doi = doi[:-1]

        return doi
    else:
        # Now search for the DOI on Crossref.
        if verbose:
            print("No inline DOI found for this reference. Trying CrossRef search...")
        url = "http://search.crossref.org/links"
        data = json.dumps([ref])
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, data=data, headers=headers)
        if r.json()["query_ok"]:
            results = r.json()["results"][0]
            if results["match"]:
                rawdoi = results["doi"]
                doi = rawdoi[rawdoi.index("10"):]  # CrossRef returns DOIs of the form http://dx.doi/org/10.<whatever>
                return doi
            else:
                if verbose:
                    print("Couldn't find a DOI, sorry!")
        else:
            print("There's a problem with the CrossRef DOI search. Check your internet connection and confirm the original paper was properly formatted in the PLOS XML style, then try again.")
        return None


def doi_batch(paper, crossref=False):
    '''
    Returns all the dois for a whole paper, in one batch.
    Works somewhat like the individual doi function above -- searches for a doi inline, then looks elsewhere if that fails --
    but this function looks at the inline HTML DOIs on the PLOS website for the DOIs by default.
    If crossref=True, it uses CrossRef instead, but it submits all the CrossRef requests at once,
    so it isn't spamming the CrossRef server the way a long series of individual doi calls would.
    '''
    # Get the doi of the given paper.
    paper_doi = plos_paper_doi(paper)
    # Find all the references.
    references = paper.find_all("ref")
    max_ref_num = len(references)
    ref_nums = list(range(1, max_ref_num + 1))
    refs = {i: r.text for i, r in zip(ref_nums, references)}
    dois = {}
    cr_queries = {}
    # Try searching for inline DOIs first.
    for i, ref in refs.items():
        doimatch = re.search(r"doi:|DOI:|Doi:|doi|DOI", ref)
        if doimatch:
            rawdoi = ref[doimatch.start():]
            try:
                doi = rawdoi[rawdoi.index("10."):]
                # all DOI's start with 10., see reference here: http://www.doi.org/doi_handbook/2_Numbering.html#2.2
            except ValueError:
                # if a ValueError is raised, that means the DOI doesn't contain the string '10.' -- which means it's not a valid DOI.
                cr_queries[i] = ref
                continue  # jump to the next reference

            # Removing whitespace and anything afterwards.
            space = re.search(r"\s", doi)
            if space:
                doi = doi[:space.start()]

            # Removing trailing periods.
            if doi[-1] == ".":
                doi = doi[:-1]

            dois[i] = doi
        else:
            cr_queries[i] = ref

    print(dois)

    if crossref:
        # Now search for the DOIs on Crossref.
        url = "http://search.crossref.org/links"
        data = json.dumps(list(cr_queries.values()))
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, data=data, headers=headers)
        if r.json()["query_ok"]:
            results = r.json()["results"]
        else:
            print("There's a problem with the CrossRef DOI search. Check your internet connection and confirm the original paper was properly formatted in the PLOS XML style, then try again.")
            return None

        for i, result in zip(list(cr_queries.keys()), results):
            if result["match"]:
                rawdoi = result["doi"]
                doi = rawdoi[rawdoi.index("10"):]  # CrossRef returns DOIs of the form http://dx.doi/org/10.<whatever>
                dois[i] = doi
            else:
                dois[i] = None
    else:
        paper_url = "http://www.plosone.org/article/info:doi/" + paper_doi
        paper_request = requests.get(paper_url)
        paper_html = BeautifulSoup(paper_request.content, "lxml")
        html_references = paper_html.select('.references > li')

        for i in cr_queries.keys():
            ref = str(html_references[i-1])
            try:
                doimatch = re.search(r"doi:|DOI:|Doi:|doi|DOI", ref)
            except TypeError:
                # if a ValueError is raised, that means that somehow, ref is not a string, which means there's something really weird with the reference.
                # Skip it and go to the next one.
                dois[i] = None
                continue  # jump to the next reference
            if doimatch:
                rawdoi = ref[doimatch.start():]
                try:
                    doi = rawdoi[rawdoi.index("10."):]
                    # all DOI's start with 10., see reference here: http://www.doi.org/doi_handbook/2_Numbering.html#2.2
                except ValueError:
                    # if a ValueError is raised, that means the DOI doesn't contain the string '10.' -- which means it's not a valid DOI.
                    dois[i] = None
                    continue  # jump to the next reference

                # Removing whitespace and anything afterwards.
                space = re.search(r"\s", doi)
                if space:
                    doi = doi[:space.start()]

                # Removing trailing periods.
                if doi[-1] == ".":
                    doi = doi[:-1]

                dois[i] = doi
            else:
                dois[i] = None
    return dois


def intra_paper_mentions(number, paper):
    '''
    DEPRECATED in favor of ipm_dictionary
    Given a soupified paper and a citation number, returns the number of times that citation number is mentioned in the given paper.
    '''
    groups = [group_cleaner(g) for g in citation_grouper(paper)]
    flat_list = list(chain(*groups))
    return flat_list.count(number)
    # And that's all, folks!


def ipm_dictionary(paper):
    '''
    Creates a dictionary of the number of intra-paper mentions for each thing cited in the given paper.
    Basically runs intra_paper_mentions on every cited thing within the given paper, then stuffs them in a database.
    MUCH faster than actually doing that, though.
    '''
    groups = [group_cleaner(g) for g in citation_grouper(paper)]
    flat_list = list(chain(*groups))
    # Find all the references.
    references = paper.find_all("ref")
    max_ref_num = len(references)
    results = {i: flat_list.count(i) for i in range(1, max_ref_num + 1)}
    return results


def ipm_histogram(paper, details=False):
    '''
    Returns a database that is essentially the inverse of what ipm_dictonary spits out:
    now the keys are the number of mentions in the paper, and the values are the number of cited things that are mentioned that many times.
    So d[1] is the number of cited things only mentioned once, etc.
    If details = True, the dictionary will instead return a list of the things with the given number of mentions.
    '''
    cite_dict = ipm_dictionary(paper)
    frequencies = set(cite_dict.values())

    if not details:
        hist = {f: 0 for f in frequencies}  # dict comprehensions FTW!
        for k in list(cite_dict.keys()):
            v = cite_dict[k]
            hist[v] += 1
    else:
        hist = {f: [] for f in frequencies}
        for k in list(cite_dict.keys()):
            v = cite_dict[k]
            hist[v].append(k)

    return hist


def micc(number, paper):
    '''
    DEPRECATED in favor of micc_dictionary
    Given a paper and a citation number within that paper,
    returns the median number of inline co-citations alongside that citation in that paper.
    '''
    # Fairly straightforward.
    all_groups = [group_cleaner(g) for g in citation_grouper(paper)]
    counts = [g.count(number) for g in all_groups]
    cite_groups = compress(all_groups, counts)
    cocite_counts = [len(g) - 1 for g in cite_groups]
    return median(cocite_counts)


def micc_dictionary(paper):
    '''
    Analogous to citation_number_dictionary, but for MICCs rather than the number of citations.
    Co-citations are when two citations are included in the same end note (e.g, '[3-5]')
    :return: dict of counts for co-citation occurrences
    '''
    all_groups = [group_cleaner(g) for g in citation_grouper(paper)]
    references = paper.find_all("ref")
    max_ref_num = len(references)
    results = {}
    for i in range(1, max_ref_num + 1):
        counts = [g.count(i) for g in all_groups]
        cite_groups = compress(all_groups, counts)
        cocite_counts = [len(g) - 1 for g in cite_groups]
        if len(cocite_counts) == 0:
            cocite_counts = [-1]
        results[i] = median(cocite_counts)

    return results


def micc_histogram(paper, details=False):
    '''
    Analogous to citation_histogram, but for MICCs rather than the number of citations.
    '''
    micc_dict = micc_dictionary(paper)
    miccs = set(micc_dict.values())

    if not details:
        hist = {m: 0 for m in miccs}
        for k in list(micc_dict.keys()):
            v = micc_dict[k]
            hist[v] += 1
    else:
        hist = {m: [] for m in miccs}
        for k in list(micc_dict.keys()):
            v = micc_dict[k]
            hist[v].append(k)

    return hist


def citation_database(papers, verbose=True):
    '''
    Given a list of soupified papers in PLOS XML format, assembles a database of the papers those papers cite,
    collects citation numbers and MICCs for each of those papers,
    and then calculates the median number of intra-paper mentions and median MICCs for each paper in the database.
    Returns a dictionary of these measures, along with bare number of citations, keyed by DOI.
    Papers without discoverable DOIs are removed from the database.
    '''
    if verbose:
        print("Processing " + str(len(papers)) + " papers...")

    database = {}

    for i, paper in enumerate(tqdm(papers)):
        if verbose:
            paper_doi = plos_paper_doi(paper)
            print("DOI of paper " + str(i + 1) + " is " + paper_doi)
        # Get the DOIs, the intra-paper mention counts, and the miccs.
        ipms = ipm_dictionary(paper)  # -> citation_counts
        miccs = micc_dictionary(paper)
        if verbose:
            print("Retrieving DOIs for paper " + str(i + 1) + "...")
        dois = doi_batch(paper)

        # Remove the papers with un-identifiable DOIs.
        dois = {k: v for k, v in compress(list(dois.items()), list(dois.values()))}
        if verbose:
            print("Retrieved " + str(len(dois)) + " DOIs.")
            print("Processing database entries...")
        for j, doi in dois.items():
            try:
                database[doi]["ipms"].append(ipms[j])
                database[doi]["miccs"].append(miccs[j])
                database[doi]["citations"] += 1
            except KeyError:
                database[doi] = {}
                database[doi]["ipms"] = [ipms[j]]
                database[doi]["miccs"] = [miccs[j]]
                database[doi]["citations"] = 1

    if verbose:
        print("Database post-processing...")
    for info in database.values():
        info["median_ipm"] = median(info["ipms"])
        info["median_micc"] = median(info["miccs"])

    return database


def paper_citations(filename, verbose=False):
    '''
    Somewhat similar to citation_database.
    Useful as a helper function in situations where there are too many papers in the corpus to hold in RAM at once.
    Given a filename for a PLOS XML paper,
    assembles a list of the papers it cites,
    collects DOIs, the number of mentions, and MICCs for each of those papers,
    Returns a dictionary of these measures, along with bare number of citations, keyed by DOI.
    Papers without discoverable DOIs are removed from the database.
    '''
    citations = {}

    paper = soupify(filename)

    # if verbose:
    paper_doi = plos_paper_doi(paper)
    print("DOI of paper is " + paper_doi)
    # Get the DOIs, the intra-paper mention counts, and the miccs.
    ipms = ipm_dictionary(paper)
    miccs = micc_dictionary(paper)
    if verbose:
        print("Retrieving DOIs for paper references...")
    dois = doi_batch(paper)
    # Remove the papers with un-identifiable DOIs.
    dois = {k: v for k, v in compress(list(dois.items()), list(dois.values()))}
    if verbose:
        print("Retrieved " + str(len(dois)) + " DOIs.")
        print("Processing database entries...")
    for j, doi in dois.items():
        citations[doi] = {}
        citations[doi]["ipms"] = ipms[j]
        citations[doi]["miccs"] = miccs[j]
        citations[doi]["citations"] = 1

    return citations


def large_citation_database(dois, xmlfolder="papers/", verbose=True, num_of_processors=8):
    '''
    Does the same thing as citation_database, but doesn't store as much information in RAM.
    Also, takes a list of DOIs as its argument, rather than a list of soupified XML papers.
    '''
    if verbose:
        print("Retrieving papers...")
    # The one-liner below does several things:
    # it retrieves the full XML text of the PLOS papers with the DOIs listed in the argument;
    # it saves the XML files to the path specified in xmlfolder, with filenames of the pattern <the part of the doi that comes after the slash>.xml;
    # it creates a list of those filenames.
    filenames = [remote_retrieve(doi, filename=xmlfolder + re.search(r"/.+", doi).group()[1:].encode("UTF-8") + ".xml") for doi in dois]

    # Prepare for multiprocessing!
    p = Pool(num_of_processors)

    # Do it!
    if verbose:
        print("Pulling citations...")
    individual_databases = p.map(paper_citations, filenames)
    # individual_databases = map(paper_citations, filenames)
    p.close()
    if verbose:
        print("Assembling citations into a database...")
    database = {}
    for db in individual_databases:
        for doi, data in db.items():
            try:
                database[doi]["ipms"].append(data["ipms"])
                database[doi]["miccs"].append(data["miccs"])
                database[doi]["citations"] += 1
            except KeyError:
                database[doi] = {}
                database[doi]["ipms"] = [data["ipms"]]
                database[doi]["miccs"] = [data["miccs"]]
                database[doi]["citations"] = 1
    if verbose:
        print("Database post-processing...")
    for info in database.values():
        info["median_ipm"] = median(info["ipms"])
        info["median_micc"] = median(info["miccs"])

    return database


def plos_search(query, query_type=None, rows=20, more_parameters=None,
                fq='''doc_type:full AND article_type_facet:"Research Article"''',
                output="json", verbose=False):
    '''
    Accesses the PLOS search API.
    query: the text of your query.
    query_type: subject, author, etc.
    rows: maximum number of results to return.
    more_parameters: an optional dictionary; key-value pairs are parameter names and values for the search api.
    fq: determines what kind of results are returned.
    Set by default to return only full documents that are research articles (almost always what you want).
    output: determines output type. Set to JSON by default, XML is also possible, along with a few others.
    Note that the PLOS search API cannot return full paper text, only abstracts and metadata.
    However, the URL for retrieving full-text PLOS papers is wholly specified by a paper's DOI (journal is not necessary).
    '''

    # This is *MY* API key. Please don't overuse it.
    # We're going to need a different one (or a different arrangement altogether) for any public release.
    api_key = "s4ZVBmgJyfZPMpqyy3Gs"  # for abecker@plos.org

    query_string = ""
    if query_type:
        query_string += query_type + ":"
    query_string += '"' + query + '"'

    params_string = ""
    if more_parameters:
        params_string = "&" + "&".join([key + "=" + quote(value) for key, value in more_parameters.items()])

    fq_string = "&fq=" + quote(fq)

    url = "http://api.plos.org/search?q=" + query_string + params_string + fq_string + "&wt=" + output + "&rows=" + str(rows) + "&api_key=" + api_key
    headers = {'Content-Type': 'application/' + output}
    if verbose:
        print(url)
    r = requests.get(url, headers=headers)
    r.encoding = "UTF-8"  # just to be sure
    return r.json()["response"]["docs"]


def plos_dois(search_results):
    '''Turns search results from plos_search into a list of DOIs.'''
    return [paper["id"] for paper in search_results]


def plos_paper_doi(paper):
    '''Given a soupified PLOS XML paper, returns that paper's DOI.'''
    paper_doi = paper.find("article-id", attrs={"pub-id-type": "doi"}).text
    return paper_doi


def zero_mentions(paper):
    '''
    Given a soupified PLOS XML paper, returns False,
    unless there are citation reference numbers in that paper's list of references that are not actually mentioned in the text of the paper.
    (This is against PLOS editorial policy, but it happens.)
    If there are such "zero-mention" citations, this function returns a tuple with two entries:
    the DOI of the given paper,
    and a list of all the zero-mention citation reference numbers.
    '''
    # Get the intra-paper mentions for everything in the list of references of the given paper.
    ipms = ipm_dictionary(paper)
    # See whether there are any references with zero mentions.
    if list(ipms.values()) and min(ipms.values()) > 0:
        print("Paper is okay!")
        return False
    else:
        print("Paper is NOT okay!")
        # Get the DOI of the offending paper
        doi = plos_paper_doi(paper)
        print(doi)
        # Get the reference numbers of the zero-mention references.
        zero_mentions = [x for x in list(ipms.items()) if not x[1]]
        print(zero_mentions)
        zero_mentions = [z[0] for z in zero_mentions]
        return (doi, zero_mentions)
