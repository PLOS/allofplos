"""These functions are for parsing individual elements of the article XML tree

Eventually these functions will probably need to be a class.
"""
import datetime
import difflib
import re
import string

import lxml.etree as et
import unidecode


def parse_article_date(date_element, date_format='%d %m %Y'):
    """
    For an article date element, convert XML to a datetime object.
    :param date_element: An article XML element that contains a date
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


def get_rid_dict(contrib_element):
    """ For an individual contributor, get the list of their associated rids.
    More about rids: https://jats.nlm.nih.gov/archiving/tag-library/1.1/attribute/rid.html
    Used in get_contrib_info().
    :param contrib_element: An article XML element with the tag <contrib>
    :return: dictionary matching each type of rid to its value for that contributor
    """
    rid_dict = {}
    contrib_elements = contrib_element.getchildren()
    # get list of ref-types
    rid_type_list = [el.attrib.get('ref-type', 'fn') for el in contrib_elements if el.tag == 'xref']

    # make dict of ref-types to the actual ref numbers (rids)
    for rid_type in set(rid_type_list):
        rid_list = [el.attrib.get('rid', None) for el in contrib_elements if el.tag == 'xref' and el.attrib.get('ref-type', 'fn') == rid_type]
        rid_dict[rid_type] = rid_list

    return rid_dict


def get_author_type(contrib_element):
    """Get the type of author for a single contributor from their accompanying <contrib> element.
    Authors can be 'corresponding' or 'contributing'. Depending on the paper, some elements have a 
    top-level "corresp" attribute that equal yes; otherwise, corresponding status can be inferred
    from the existence of the <xref> attribute ref-type="corresp"
    :param contrib_element: An article XML element with the tag <contrib>
    :return: author type (corresponding, contributing, None)
    """
    answer_dict = {
        "yes": "corresponding",
        "no": "contributing"
    }

    author_type = None
    if contrib_element.get('contrib-type', None) == 'author':
        corr = contrib_element.get('corresp', None)
        if corr:
            author_type = answer_dict.get(corr, None)
        else:
            temp = get_rid_dict(contrib_element).get('corresp', None)
            if temp:
                author_type = answer_dict.get("yes", None)
            else:
                author_type = answer_dict.get("no", None)

    return author_type


def get_contrib_name(contrib_element):
    """Get the name for a single contributor from their accompanying <contrib> element.
    Also constructs their initials for later matching to article-level dictionaries about
    contributors, including get_aff_dict() and get_fn_dict().
    Can also handle 'collab' aka group authors with a group name but no surname or given names.
    :param contrib_element: An article XML element with the tag <contrib>
    :return: dictionary of a single contributor's given names, surname, initials, and group name
    """
    given_names = ''
    surname = ''

    contrib_name_element = contrib_element.find("name")
    if contrib_name_element is not None:
        for name_element in contrib_name_element.getchildren():
            if name_element.tag == 'surname':
                # for some reason, name_element.text doesn't work for this element
                surname = (et.tostring(name_element,
                                       encoding='unicode',
                                       method='text').rstrip(' ').rstrip('\t').rstrip('\n')
                           or "")
            elif name_element.tag == 'given-names':
                given_names = name_element.text
                if given_names == '':
                    print("given names element.text didn't work")
                    given_names = (et.tostring(name_element,
                                               encoding='unicode',
                                               method='text').rstrip(' ').rstrip('\t').rstrip('\n')
                                   or "")
            else:
                pass
        if given_names or surname:
            # construct initials if either given or surname is present
            try:
                contrib_initials = ''.join([part[0].upper() for part in re.split('[-| |,|\.]+', given_names) if part]) + \
                                  ''.join([part[0] for part in re.split('[-| |,|\.]+', surname) if part[0] in string.ascii_uppercase])
            except IndexError:
                contrib_initials = ''
            contrib_name = dict(contrib_initials=contrib_initials,
                                given_names=given_names,
                                surname=surname)
    else:
        # if no <name> element found, assume it's a collaboration
        contrib_collab_element = contrib_element.find("collab")
        group_name = et.tostring(contrib_collab_element, encoding='unicode')
        group_name = re.sub('<[^>]*>', '', group_name).rstrip('\n')
        if not group_name:
            print("Error constructing contrib_name group element")
            group_name = ''
        contrib_name = dict(group_name=group_name)

    return contrib_name


def get_contrib_ids(contrib_element):
    """Get the ids for a single contributor from their accompanying <contrib> element.
    This will mostly get ORCID IDs, and indicate whetherh they are authenticated.
    For more information of ORCIDs, see https://orcid.org/
    :param contrib_element: An article XML element with the tag <contrib>
    :return: list of dictionaries of ids for that contributor
    """
    id_list = []
    for item in contrib_element.getchildren():
        if item.tag == 'contrib-id':
            contrib_id_type = item.attrib.get('contrib-id-type', None)
            contrib_id = item.text
            contrib_authenticated = item.attrib.get('authenticated', None)
            id_dict = dict(id_type=contrib_id_type,
                           id=contrib_id,
                           authenticated=contrib_authenticated
                           )
            id_list.append(id_dict)

    return id_list


def get_credit_taxonomy(contrib_element):
    """Get the contributor roles from the CREDiT taxonomy element when it is present.
    Right now, this is is equivalent to author roles.
    For more information about this data structure, see http://dictionary.casrai.org/Contributor_Roles
    :param contrib_element: An article XML element with the tag <contrib>
    :return: dictionary of contributor roles for an individual contributor

    """
    credit_dict = {}
    for item in contrib_element.getchildren():
        if item.tag == 'role':
            content_type = item.attrib.get('content-type', None)
            if content_type == 'http://credit.casrai.org/':
                content_type = 'CASRAI CREDiT taxonomy'
            role = item.text
            if not credit_dict.get(content_type, None):
                credit_dict[content_type] = [role]
            else:
                credit_dict[content_type].append(role)
    return credit_dict


def match_contrib_initials_to_dict(contrib_dict, special_dict, matched_keys, contrib_key):
    """For an individual contributor, match their initials to a dictionary.
    This is used for both matching contributors to email addresses as well as credit roles,
    where the keys for all dictionaries are contributor initials. In contrib_dict, these initials are
    constructed from the contributor name in get_contrib_name(). For the special dicts, initials are
    provided in the raw XML.
    See match_contribs_to_dicts() for how this matching process is iterated across contributors.
    :param contrib_dict: information about individual contributor, including their name and constructed initials
    :param special_dict: usually either get_aff_dict() or get_credit_dict()
    :param matched_keys: list of keys in special_dict already matched that will be excluded
    :param contrib_key: The item in the contrib dictionary where the matched special_dict will be stored
    :return: updated contrib_dict that includes the newly matched special_dict
    """
    contributor_initials = contrib_dict.get('contrib_initials')
    # special_dict keys (initials) are assumed to be uppercase
    special_dict = {k.upper(): v
                    for k, v in special_dict.items()
                    if k not in matched_keys}
    if contrib_dict.get('group_name', None) is None:
        try:
            contrib_dict[contrib_key] = special_dict[contributor_initials.upper()]
        except KeyError:
            # Sometimes middle initials are included or excluded, so restrict both initial sets to
            # first and last initial only.
            try:
                contributor_abbrev_initials = ''.join([contributor_initials[0], contributor_initials[-1]])
                for dict_initials, dict_value in special_dict.items():
                    if contributor_abbrev_initials == ''.join([dict_initials[0], dict_initials[-1]]).upper():
                        contrib_dict[contrib_key] = dict_value
                        break
            except (IndexError, KeyError) as e:
                pass

    return contrib_dict


def get_contrib_info(contrib_element):
    """Get a dictionary of information for a single contributor from their accompanying <contrib> element.
    Don't call this function directly. Instead, use as a part of get_contributors_info()
    This includes all contributor information that can be directly accessed from <contrib> element contents.
    However, other contributor information is stored in article-level dictionaries that need to be matched
    for each contributor using the rid_dict created here.
    :param contrib_element: An article XML element with the tag <contrib>
    :return: dictionary of contributor name, ids/ORCID, rid_dict, author_roles
    """
    # get their name
    contrib_dict = get_contrib_name(contrib_element)

    # get contrib type
    try:
        contrib_dict['contrib_type'] = contrib_element.attrib['contrib-type']
    except KeyError:
        # invalid contributor field; shouldn't count as contributor
        return None

    # get author type
    if contrib_dict.get('contrib_type') == 'author':
        contrib_dict['author_type'] = get_author_type(contrib_element)
    elif contrib_dict.get('contrib_type') == 'editor':
        for item in contrib_element.getchildren():
            if item.tag == 'Role' and item.text.lower() != 'editor':
                print('new editor type: {}'.format(item.text))
                contrib_dict['editor_type'] = item.text

    # get ORCID, if available
    contrib_dict['ids'] = get_contrib_ids(contrib_element)

    # get dictionary of contributor's footnote types to footnote ids
    contrib_dict['rid_dict'] = get_rid_dict(contrib_element)

    # get dictionary of CREDiT taxonomy, if available
    contrib_dict['author_roles'] = get_credit_taxonomy(contrib_element)

    return contrib_dict


def match_author_names_to_emails(corr_author_list, email_dict):
    """ Finds the best match of author names to potential matching email addresses.
    Don't call directly, but use as a part of match_contribs_to_dicts().
    Sometimes, the initials-matching process in match_contrib_initials_to_dict() fails. When there's
    at least two ummatched corresponding authors and email addresses, this function
    figures out the name/email matching with the highest matching continguous character count and matches them.
    This is a 'hail Mary' that thankfully also has a high rate of accuracy.
    :param corr_author_list: list of contrib_dicts for corresponding authors with no email field
    :param email_dict: list of unmatched author email addresses
    :return: list of updated contrib_dicts for each author, now including an email field
    """
    overall_matching_dict = {}
    match_values = []
    # Step 1: for each author and email combination, compute longest common string
    for corr_author in corr_author_list:
        # make single string of author full name
        seq_1 = unidecode.unidecode(''.join([corr_author.get('given_names'), corr_author.get('surname')]).lower())
        matching_dict = {}
        for email_initials, email_address in email_dict.items():
            # make string of email address that doesn't include domain
            seq_2 = unidecode.unidecode(email_address[0].lower().split('@')[0])
            matcher = difflib.SequenceMatcher(a=seq_1, b=seq_2)

            # construct dictionary with name, email, and matching string length for each pair
            match = matcher.find_longest_match(0, len(matcher.a), 0, len(matcher.b))
            matching_dict[tuple(email_address)] = match[-1]
            # add length of match to list of all match lengths
            match_values.append(match[-1])
        overall_matching_dict[(corr_author.get('given_names'), corr_author.get('surname'))] = matching_dict
    # Step 2: for the author and email combination(s) with the longest common string, match them
    # Iterate through max_values in descending order until all are matched
    newly_matched_emails = []
    newly_matched_authors = []
    count = 0
    while len(newly_matched_emails) < len(overall_matching_dict) and count < 20:
        for k1, v1 in overall_matching_dict.items():
            for k2, v2 in v1.items():
                if v2 == max(match_values):
                    for corr_author in corr_author_list:
                        if k1 == (corr_author.get('given_names'), corr_author.get('surname')) \
                         and k2 not in newly_matched_emails and k1 not in newly_matched_authors:
                            corr_author['email'] = list(k2)
                            # keep track of matched email & author so they're not matched again
                            newly_matched_authors.append(k1)
                            newly_matched_emails.append(k2)
                            match_values.remove(v2)
            count += 1
    # Step 3: match the remaining author and email if there's only one remaining (most common)
    # Might not be necessary with the while loop
    still_unmatched_authors = [author for author in corr_author_list if not author.get('email')]
    still_unmatched_emails = {k: v for k, v in email_dict.items() if tuple(v) not in newly_matched_emails}
    if len(still_unmatched_authors) == len(still_unmatched_emails) <= 1:
        if len(still_unmatched_authors) == len(still_unmatched_emails) == 1:
            # only one remaining. it gets matched
            still_unmatched_authors[0]['email'] = list(still_unmatched_emails.values())[0]
        else:
            # we were successful at matching all emails (likely, two pairs had the same match values)
            pass
    else:
        # something's gone wrong. the candidate list of emails doesn't match the number of authors
        # the corresponding authors printed below will have their ['email'] field unfilled
        print('not calculating right', still_unmatched_authors, still_unmatched_emails)

    return corr_author_list


def match_contribs_to_dicts(contrib_list, special_dict, contrib_key):
    """
    :param contrib_list: list of contributors
    :param special_dict: usually either get_aff_dict() or get_credit_dict()
    :param contrib_key: The item in the contrib dictionary where the matched special_dict will be stored
    """
    matching_error = False
    matched_keys = []
    for contrib_dict in contrib_list:
        contrib_dict = match_contrib_initials_to_dict(contrib_dict,
                                                      special_dict,
                                                      matched_keys,
                                                      contrib_key)
        if contrib_dict.get(contrib_key, None):
            for k, v in special_dict.items():
                if v == contrib_dict.get(contrib_key):
                    matched_keys.append(k)
    if len(special_dict) == len(matched_keys):
        # all special_dicts and contributors are matched
        pass
    else:
        unmatched_special_dict = {k: v for k, v in special_dict.items()
                                  if k not in matched_keys}
        contrib_dict_missing_special_list = [contrib_dict for contrib_dict in contrib_list
                                             if not contrib_dict.get(contrib_key, None)]

        # if one contributor and one special_dict are unmatched, match them
        if len(unmatched_special_dict) == len(contrib_dict_missing_special_list) == 1:
            contrib_dict_missing_special_list[0][contrib_key] = list(unmatched_special_dict.values())[0]

        elif len(unmatched_special_dict) != len(contrib_dict_missing_special_list):
            # these numbers should always be the same
            matching_error = True

        else:
            if contrib_key == 'email':
                # match remaining contributor names to emails by string matching
                contrib_dicts = match_author_names_to_emails(contrib_dict_missing_special_list, unmatched_special_dict)
                if len([contrib for contrib in contrib_dicts if contrib_key not in contrib.keys()]) == 0:
                    # finally every contributor and special_dict is matched
                    pass
                else:
                    # even after applying every strategy, there were unmatched contributors
                    matching_error = True
    return contrib_list, matching_error
