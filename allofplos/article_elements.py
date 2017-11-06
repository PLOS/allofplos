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


def get_rid_dict(contrib_element):
    rid_dict = {}
    contrib_elements = contrib_element.getchildren()
    # get list of ref-types
    rid_type_list = [el.attrib['ref-type'] for el in contrib_elements if el.tag == 'xref']
    # make dict of ref-types to the actual ref numbers (rids)
    for rid_type in set(rid_type_list):
        rid_list = [el.attrib['rid'] for el in contrib_elements if el.tag == 'xref' and el.attrib['ref-type'] == rid_type]
        rid_dict[rid_type] = rid_list

    return rid_dict


def get_author_type(contrib_element):

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
        if bool(given_names) or bool(surname):
            try:
                contrib_initials = ''.join([part[0].upper() for part in re.split('[-| |,|\.]+', given_names) if part]) + \
                                  ''.join([part[0] for part in re.split('[-| |,|\.]+', surname) if part[0] in string.ascii_uppercase])
            except IndexError:
                contrib_initials = ''
            contrib_name = dict(contrib_initials=contrib_initials,
                                given_names=given_names,
                                surname=surname)
    else:
        contrib_collab_element = contrib_element.find("collab")
        if contrib_collab_element.text:
            group_name = contrib_collab_element.text
        else:
            group_name = et.tostring(contrib_collab_element, encoding='unicode')
            group_name = re.sub('<[^>]*>', '', group_name).rstrip('\n')
            if not group_name:
                print("Error constructing contrib_name group element")
                group_name = ''
        contrib_name = dict(group_name=group_name)

    return contrib_name


def get_contrib_ids(contrib_element):
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
    contributor_initials = contrib_dict.get('contrib_initials')
    # special_dict keys (initials) are assumed to be uppercase
    special_dict = {k.upper(): v
                    for k, v in special_dict.items()
                    if k not in matched_keys}
    try:
        contrib_dict[contrib_key] = special_dict[contributor_initials.upper()]
    except KeyError:
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
    # get their name
    contrib_dict = get_contrib_name(contrib_element)

    # get contrib type
    contrib_dict['contrib_type'] = contrib_element.attrib['contrib-type']

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
    overall_matching_dict = {}
    match_values = []
    # Step 1: for each author and email combination, compute longest common string
    for corr_author in corr_author_list:
        seq_1 = unidecode.unidecode(''.join([corr_author.get('given_names'), corr_author.get('surname')]).lower())
        matching_dict = {}
        for email_initials, email_address in email_dict.items():
            seq_2 = unidecode.unidecode(email_address[0].lower().split('@')[0])
            matcher = difflib.SequenceMatcher(a=seq_1, b=seq_2)
            match = matcher.find_longest_match(0, len(matcher.a), 0, len(matcher.b))
            matching_dict[email_address[0]] = match[-1]
            match_values.append(match[-1])
        overall_matching_dict[corr_author.get('surname')] = matching_dict

    # Step 2: for the author and email combination(s) with the longest common string, match them
    newly_matched_emails = []
    for k1, v1 in overall_matching_dict.items():
        for k2, v2 in v1.items():
            if v2 == max(match_values):
                for corr_author in corr_author_list:
                    if k1 == corr_author.get('surname') and k2 not in newly_matched_emails:
                        corr_author['email'] = k2
                        newly_matched_emails.append(k2)
    # Step 3: match the remaining author and email if there's only one
    still_unmatched_authors = [author for author in corr_author_list if 'email' not in author.keys()]
    still_unmatched_emails = {k: v for k, v in email_dict.items() if v[0] not in newly_matched_emails}
    if len(still_unmatched_authors) == len(still_unmatched_emails) <= 1:
        if len(still_unmatched_authors) == len(still_unmatched_emails) == 1:
            still_unmatched_authors[0]['email'] = list(still_unmatched_emails.values())[0]
    else:
        print('not calculating right', still_unmatched_authors, still_unmatched_emails)

    return corr_author_list


def match_contribs_to_dicts(contrib_list, special_dict, contrib_key):
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
