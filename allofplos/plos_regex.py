import numpy as np
import re

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


def validate_doi(doi):
    """
    For an individual string, tests whether the full string is a valid PLOS DOI or not
    Example: '10.1371/journal.pbio.2000777' is True, but '10.1371/journal.pbio.2000777 ' is False
    :return: True if a valid PLOS DOI; False if not
    """
    return make_regex_bool(full_doi_regex_match.search(doi))


def find_valid_dois(doi):
    """
    For an individual string, searches for any valid PLOS DOIs within it and returns them
    :return: list of valid PLOS DOIs contained within string
    """
    return full_doi_regex_search.findall(doi)


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