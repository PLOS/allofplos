import datetime
import os
import re
import subprocess

import lxml.etree as et
from lxml import objectify
import requests

from . import get_corpus_dir
from .transformations import (filename_to_doi, _get_base_page, LANDING_PAGE_SUFFIX,
                              URL_SUFFIX, plos_page_dict, doi_url)
from .plos_regex import validate_doi
from .elements import (parse_article_date, get_contrib_info,
                       Journal, License, match_contribs_to_dicts)


class Article():
    """The primary object of a PLOS article, initialized by a valid PLOS DOI.

    """
    def __init__(self, doi, directory=None):
        """Creation of an article object.

        Usage:
        For the first time, you can use
        `article = Article(doi)`
        and then it and some attributes will be stored in memory.
        For creating articles after the first one, you can use:
        `article.doi = doi`
        This preserves the generic attributes and erases the article-specific ones
        (See also reset_memoized_attrs())
        Use this to more rapidly iterate through different articles.
        :param doi: The Digital Object Identifier of the article
        :type doi: str
        :param directory: where the local article XML file is located, defaults to None
        :type directory: str, optional
        """
        self.doi = doi
        self.directory = directory if directory else get_corpus_dir()
        self.reset_memoized_attrs()
        self._editor = None
    
    def __eq__(self, other):
        doi_eq = self.doi == other.doi
        dir_eq = self.directory == other.directory
        return doi_eq and dir_eq

    def reset_memoized_attrs(self):
        """Reset attributes to None when instantiating a new article object.

        For article attributes that are memoized and specific to that particular article
        (including the XML tree and whether the xml file is in the local directory),
        reset them when creating a new article object.
        """
        self._tree = None
        self._local = None
        self._contributors = None

    @property
    def doi(self):
        """The unique Digital Object Identifier for a PLOS article.

        See https://www.doi.org/
        :returns: DOI of the article object
        :rtype: {str}
        """
        return self._doi

    @property
    def text_viewer(self):
        """Command line application for viewing text to be used with
        open_in_viewer.

        Defaults to "open", which opens in whatever the default application is
        in your operating system for files ending in ".xml".

        Persists across article objects.
        Use with self.open_in_viewer() to open an article of interest.

        Check your text viewers documentation to learn how to launch it from the command line.
        For Sublime Text, see http://docs.sublimetext.info/en/latest/command_line/command_line.html
        :returns: command line shortcut for the text viewer
        :rtype: {str}
        """
        try:
            return self._text_viewer
        except AttributeError as e:
            print(("{}:\n"
                   "You need to assign a non-terminal text viewer "
                   "command able to be run on the CLI to self.text_viewer"
                   ).format(e))

    @text_viewer.setter
    def text_viewer(self, value="open"):
        """Sets the text viewer for all article objects.

        :param value: from self.text_viewer
        :type value: {str}
        """
        self._text_viewer = value

    @doi.setter
    def doi(self, d):
        """
        Using regular expressions, make sure the doi is valid before
        instantiating the article object.
        """
        if validate_doi(d) is False:
            raise Exception("Invalid format for PLOS DOI: {}".format(d))
        self.reset_memoized_attrs()
        self._doi = d

    def __str__(self, exclude_refs=True):
        """Output when you print an article object on the command line.

        For parsing and viewing the XML of a local article. Should not be used for hashing
        Excludes <back> element (including references list) for easier viewing
        :param exclude_refs: remove references from the article tree (eases print viewing)
        """
        parser = et.XMLParser(remove_blank_text=True)
        tree = et.parse(self.filename, parser)
        if exclude_refs:
            root = tree.getroot()
            back = tree.xpath('./back')
            root.remove(back[0])
        local_xml = et.tostring(tree,
                                method='xml',
                                encoding='unicode',
                                pretty_print=True)
        return local_xml

    def __repr__(self):
        """Value of an article object when you call it directly on the command line.

        Shows the DOI and title of the article
        :returns: DOI and title
        :rtype: {str}
        """
        out = "DOI: {0}\nTitle: {1}".format(self.doi, self.title)
        return out

    def doi_link(self):
        """The link of the DOI, which redirects to the journal URL."""
        return doi_url + self.doi

    def get_remote_xml(self):
        """For an article, parse its XML file at the location of self.url.

        Uses the lxml element tree to create the string, which is saved to a local
        file when downloaded
        :returns: string of entire remote article file
        :rtype: {str}
        """
        remote_xml = et.tostring(self.remote_tree,
                                 method='xml',
                                 encoding='unicode')
        return remote_xml

    def open_in_viewer(self, text_viewer=None):
        """Open a local article file of interest in an external text viewer.

        :param text_viewer: set via self.text_viewer, defaults to None
        :type text_viewer: str, optional
        :raises: TypeError
        """
        if not (text_viewer or self.text_viewer):
            raise TypeError("You have not specified an text_viewer. Please do so.")

        subprocess.call([self._text_viewer, self.filename])

    def open_in_browser(self):
        """Opens the landing page (HTML) of an article in default browser.

        This is also the URL that the DOI resolves to
        """
        subprocess.call(["open", self.page])

    def get_element_xpath(self, tag_path_elements=None, remote=False):
        """For a local article's root element, grab particular sub-elements via XPath location.

        Defaults to reading the element location for uncorrected proofs/versions of record
        The basis of every method and property looking for particular metadata fields
        :param article_root: the xml file for a single article
        :param tag_path_elements: xpath location in the XML tree of the article file
        :param remote: whether using the remote XML in self.remote_tree (defaults to False)
        :return: list of elements in the article with that xpath location
        """
        if tag_path_elements is None:
            tag_path_elements = ('/',
                                 'article',
                                 'front',
                                 'article-meta',
                                 'custom-meta-group',
                                 'custom-meta',
                                 'meta-value')
        tag_location = '/'.join(tag_path_elements)
        if remote:
            root = self.remote_tree.getroot()
        else:
            root = self.root
        return root.xpath(tag_location)

    def get_dates(self, string_=False, string_format='%Y-%m-%d'):
        """For an individual article, get all of its dates, including publication date (pubdate), submission date.

        Defaults to datetime objects
        :param string_: whether to return dates as a dictionary of strings
        :param string_format: if string_ is True, the format to return the dates in
        :return: dict of date types mapped to datetime objects for that article
        :rtype: {dict}
        """
        dates = {}
        # first location is where pubdate and date added to collection are
        tag_path_1 = ["/",
                      "article",
                      "front",
                      "article-meta",
                      "pub-date"]
        element_list_1 = self.get_element_xpath(tag_path_elements=tag_path_1)
        for element in element_list_1:
            pub_type = element.get('pub-type')
            try:
                date = parse_article_date(element)
            except ValueError:
                print('Error getting pubdates for {}'.format(self.doi))
                date = ''
            dates[pub_type] = date

        # second location is where historical dates are, including submission and acceptance
        tag_path_2 = ["/",
                      "article",
                      "front",
                      "article-meta",
                      "history"]
        element_list_2 = self.get_element_xpath(tag_path_elements=tag_path_2)
        for element in element_list_2:
            for part in element:
                date_type = part.get('date-type')
                try:
                    date = parse_article_date(part)
                except ValueError:
                    print('Error getting history dates for {}'.format(self.doi))
                    date = ''
                dates[date_type] = date

        # third location is for vor updates when it's updated (see `proof(self)`)
        rev_date = ''
        if self.proof == 'vor_update':
            tag_path = ('/',
                        'article',
                        'front',
                        'article-meta',
                        'custom-meta-group',
                        'custom-meta')
            xpath_results = self.get_element_xpath(tag_path_elements=tag_path)
            for result in xpath_results:
                if result.xpath('./meta-name')[0].text == 'Publication Update':
                    rev_date_string = result.xpath('./meta-value')[0].text
                    rev_date = datetime.datetime.strptime(rev_date_string, '%Y-%m-%d')
                    break
                else:
                    pass
        dates['updated'] = rev_date

        if string_:
            # can return dates as strings instead of datetime objects if desired
            for key, value in dates.items():
                if value:
                    dates[key] = value.strftime(string_format)

        return dates

    def dates_debug(self):
        """Whether the dates in self.get_dates() are in the correct order.

        check whether date received is before date accepted, is before pubdate
        accounts for potentially missing date fields
        :return: if dates are in right order or not
        :rtype: bool
        """
        dates = self.get_dates()
        if dates.get('received', '') and dates.get('accepted', ''):
            if dates['received'] <= dates['accepted'] <= dates['epub']:
                order_correct = True
            else:
                order_correct = False
        elif dates.get('received', ''):
            if dates['received'] <= dates['epub']:
                order_correct = True
            else:
                order_correct = False
        elif dates.get('accepted', ''):
            if dates['accepted'] <= dates['epub']:
                order_correct = True
            else:
                order_correct = False
        else:
            order_correct = True

        return order_correct

    @property
    def volume(self):
        """Volume of the article."""
        return int(self.root.xpath('/article/front/article-meta/volume')[0].text)

    @property
    def issue(self):
        """Issue of the article."""
        return int(self.root.xpath('/article/front/article-meta/issue')[0].text)

    @property
    def elocation(self):
        """Elocation ID of the article."""
        return self.root.xpath('/article/front/article-meta/elocation-id')[0].text

    def get_aff_dict(self):
        """For a given PLOS article, get list of contributor-affiliated institutions.

        Uses "rid"s to map individual contributors to their institutions
        More about rids: https://jats.nlm.nih.gov/archiving/tag-library/1.1/attribute/rid.html
        See also get_rid_dict()
        :returns: Dictionary of footnote ids to institution information
        :rtype: {dict}
        """
        tags_to_aff = ["/",
                       "article",
                       "front",
                       "article-meta"]
        article_aff_elements = self.get_element_xpath(tag_path_elements=tags_to_aff)
        aff_dict = {}
        aff_elements = [el
                        for aff_element in article_aff_elements
                        for el in aff_element.getchildren()
                        ]
        for el in aff_elements:
            if el.tag == 'aff':
                if el.getchildren():
                    for sub_el in el.getchildren():
                        if sub_el.tag == 'addr-line':
                            try:
                                aff_text_fixed = ' '.join([aff_string.strip() for aff_string in sub_el.text.splitlines()])
                            except AttributeError:
                                aff_text_fixed = et.tostring(sub_el, encoding='unicode', method='text')
                            aff_dict[el.attrib['id']] = aff_text_fixed
                else:
                    # the address for some affiliations is not wrapped in an addr-line tag
                    aff_dict[el.attrib['id']] = el.text.replace('\n', '').replace('\r', '').replace('\t', '')
        return aff_dict

    def get_fn_dict(self):
        """For a given PLOS article, get list of footnotes.

        Used with rids to map individual contributors to their institutions
        More about rids: https://jats.nlm.nih.gov/archiving/tag-library/1.1/attribute/rid.html
        See also get_rid_dict()
        :returns: Dictionary of footnote ids to institution information
        :rtype: {dict}
        """
        tags_to_fn = ["/",
                      "article",
                      "front",
                      "article-meta",
                      "author-notes"]
        article_fn_elements = self.get_element_xpath(tag_path_elements=tags_to_fn)
        fn_dict = {}
        fn_elements = [el
                       for fn_element in article_fn_elements
                       for el in fn_element.getchildren()
                       ]
        for el in fn_elements:
            if el.attrib.get('id'):
                if el.getchildren():
                    for sub_el in el.getchildren():
                        if sub_el.tag == 'email':
                            pass
                        else:
                            fn_dict[el.attrib['id']] = sub_el.text
                else:
                    # in case is at top-level of element
                    fn_dict[el.attrib['id']] = el.text.replace('\n', '').replace('\r', '').replace('\t', '')
        return fn_dict

    def get_corr_author_emails(self):
        """For an article, grab the email addresses of the corresponding authors.
        Parses the list of emails and groups by rid or by initials, if present.
        Can handle multiple emails for multiple authors if formatted correctly.
        The email addresses are in an element of author notes. While most articles have one corresponding
        author with one email address, sometimes there are 1) multiple authors, and/or 2) multiple emails per
        author. In the first case, author initials are used in the text to separate emails. In the second case,
        a comma is used to separate emails. Initials are how emails can be matched to multiple
        authors. See also `match_author_names_to_emails()` for the back-up method of name matching.
        :return: dictionary of rid or author initials mapped to list of email address(es)
        :rtype: {dict}
        """
        tag_path = ["/",
                    "article",
                    "front",
                    "article-meta",
                    "author-notes"]
        try:
            author_notes_element = self.get_element_xpath(tag_path_elements=tag_path)[0]
        except IndexError:
            # no emails found
            return {}
        corr_emails = {}
        email_list = []
        for note in author_notes_element:
            if note.tag == 'corresp':
                author_info = note.getchildren()
                for i, item in enumerate(author_info):
                    # if author initials are in the same field as email address
                    if item.tag == 'email' and item.text and all(x in item.text for x in ('(', ')')):
                        email_info = item.text.split(' ')
                        for i, info in enumerate(email_info):
                            # prune out non-letters from initials & email
                            email_info[i] = re.sub(r'[^a-zA-Z0-9=@\.+-]', '', info)
                        try:
                            corr_emails[email_info[1]] = [email_info[0]]
                        except IndexError:
                            print('Error parsing emails for {}'.format(self.doi))
                            pass

                    # if no author initials (one corr author)
                    elif item.tag == 'email' and item.tail is None and item.text:
                        email_list.append(item.text)
                        if item.text == '':
                            print('No email available for {}'.format(self.doi))
                        if note.attrib['id']:
                            corr_emails[note.attrib['id']] = email_list
                        else:
                            corr_emails['cor001'] = email_list

                    # if more than one email per author; making sure no initials present (comma ok)
                    elif item.tag == 'email' and re.sub(r'[^a-zA-Z0-9=]', '', str(item.tail)) is None:
                        try:
                            if author_info[i+1].tail is None:
                                email_list.append(item.text)
                            elif author_info[i+1].tail:
                                corr_initials = re.sub(r'[^a-zA-Z0-9=]', '', author_info[i+1].tail)
                                if not corr_emails.get(corr_initials):
                                    corr_emails[corr_initials] = [item.text]
                                else:
                                    corr_emails[corr_initials].append(item.text)
                        except IndexError:
                            email_list.append(item.text)
                            corr_emails[note.attrib['id']] = email_list
                            if i > 1:
                                print('Error handling multiple email addresses for {} in {}'
                                      .format(et.tostring(item), self.doi))
                        if item.text == '':
                            print('No email available for {}'.format(self.doi))

                    # if author initials included (more than one corr author)
                    elif item.tag == 'email' and item.tail:
                        corr_email = item.text
                        corr_initials = re.sub(r'[^a-zA-Z0-9=]', '', item.tail)
                        if not corr_initials:
                            try:
                                corr_initials = re.sub(r'[^a-zA-Z0-9=]', '', author_info[i+1].tail)
                            except (IndexError, TypeError) as e:
                                corr_initials = note.attrib['id']
                                if not corr_initials:
                                    print('email parsing is weird for', self.doi)
                        if not corr_emails.get(corr_initials):
                            corr_emails[corr_initials] = [corr_email]
                        else:
                            corr_emails[corr_initials].append(corr_email)
                    else:
                        pass
        if not corr_emails:
            author_notes_field = et.tostring(author_notes_element, method='text', encoding='unicode')
            if '@' in author_notes_field:
                regex_email = r'[\w\.-]+@[\w\.-]+'
                email_finder = re.compile(regex_email)
                email_list = email_finder.findall(author_notes_field)
                if email_list:
                    corr_emails['cor001'] = email_list
        return corr_emails

    def get_contributions_dict(self):
        """For articles that don't use the CREDiT taxonomy, compile a dictionary of author
        contribution types matched to author initials.
        Work in progress!!
        Works for highly formatted lists with subelements (e.g. '10.1371/journal.pone.0170354') and structured single strings
        (e.g. '10.1371/journal.pone.0050782'), but still fails for unusual strings (e.g, '10.1371/journal.pntd.0000072')
        See also get_credit_taxonomy() for the CREDiT taxonomy version.
        TODO: Use regex to properly separate author roles from initials for unusual strings.
        :return: dictionary mapping author initials to their author contributions/roles.
        """
        if self.type_ in ['correction', 'retraction', 'expression-of-concern']:
            # these article types don't have proper 'authors'
            return {}
        tag_path = ["/",
                    "article",
                    "front",
                    "article-meta",
                    "author-notes"]
        try:
            author_notes_element = self.get_element_xpath(tag_path_elements=tag_path)[0]
        except IndexError:
            return {}
        author_contributions = {}
        contrib_dict = {}
        initials_list = []
        for note in author_notes_element:
            if note.attrib.get('fn-type', None) == 'con':
                try:
                    # for highly structured lists with sub-elements for each item
                    # Example: 10.1371/journal.pone.0170354'
                    con_element = note[0][0]
                    con_list = con_element.getchildren()
                    for con_item in con_list:
                        try:
                            contribution = con_item[0][0].text.rstrip(':')
                            contributor_initials = (con_item[0][0].tail.lstrip(' ').rstrip('.')).split(' ')
                            initials_list.extend(contributor_initials)
                            contrib_dict[contribution] = contributor_initials
                        except (IndexError, AttributeError) as e:
                            print('Error parsing contributions item {}: {}'.format(self.doi, et.tostring(con_item,
                                                                                                         encoding='unicode',
                                                                                                         method='xml')))
                            pass
                except IndexError:
                    # for single strings, though it doesn't parse all of them correctly.
                    # Example: '10.1371/journal.pone.0050782'
                    contributions = note[0].text
                    if contributions is None:
                        print('Error parsing contributions for {}: {}'.format(self.doi, et.tostring(con_element,
                                                                                                    encoding='unicode',
                                                                                                    method='xml')))
                        return {}
                    contribution_list = re.split(': |\. ', contributions)
                    contribb_dict = dict(list(zip(contribution_list[::2], contribution_list[1::2])))
                    for k, v in contribb_dict.items():
                        v_new = v.split(' ')
                        v_new = [v.rstrip('.').strip('\n') for v in v_new]
                        contrib_dict[k.strip('\n')] = v_new
                        initials_list.extend(v_new)

        for initials in (set(initials_list)):
            contrib_list = []
            for k, v in contrib_dict.items():
                if initials in v:
                    contrib_list.append(k)
            author_contributions[initials] = contrib_list
        return author_contributions

    def get_contributors_info(self):
        """Get and organize information about each contributor for an article.
        This includes both authors and editors of the article.
        This function both creates article-level dictionaries of contributor information,
        as well as parses individual <contrib> elements. It reconciles the dicts together
        using a number of external functions from article_elements.py
        :returns: dictionary of metadata for each <contrib> element
        :rtype: list of dicts
        """

        # TODO: param to remove unnecessary fields (initials) and dicts (rid_dict)
        # TODO: also get funding information, data availability, COI, etc

        # get dictionary of ids to institutional affiliations & all other footnotes
        aff_dict = self.get_aff_dict()
        fn_dict = self.get_fn_dict()
        aff_dict.update(fn_dict)
        matching_error = False

        # get dictionary of corresponding author email addresses
        email_dict = self.get_corr_author_emails()

        # get author contributions (if no credit taxonomy)
        credit_dict = self.get_contributions_dict()

        # get list of contributor elements (one per contributor)
        tag_path = ["/",
                    "article",
                    "front",
                    "article-meta",
                    "contrib-group",
                    "contrib"]
        contrib_list = self.get_element_xpath(tag_path_elements=tag_path)
        contrib_dict_list = []

        error_printed = False

        # iterate through each contributor
        for contrib in contrib_list:
            # initialize contrib dict with default fields
            contrib_keys = ['contrib_initials',
                            'given_names',
                            'surname',
                            'group_name',
                            'ids',
                            'rid_dict',
                            'contrib_type',
                            'author_type',
                            'editor_type',
                            'email',
                            'affiliations',
                            'author_roles',
                            'footnotes'
                            ]
            contrib_dict = dict.fromkeys(contrib_keys, None)
            try:
                contrib_dict.update(get_contrib_info(contrib))
            except TypeError:
                # minimize number of times this prints out
                if not error_printed:
                    print('Error getting contrib info for {}'.format(self.doi, self.type_))
                    error_printed = True
                else:
                    pass

            # map affiliation footnote ids to the actual institutions
            try:
                if contrib_dict.get('rid_dict', None) is not None:
                    contrib_dict['affiliations'] = [aff_dict.get(aff, "")
                                                    for k, v in contrib_dict['rid_dict'].items()
                                                    for aff in v
                                                    if k == 'aff'
                                                    ]
            except (TypeError, AttributeError) as e:
                print('error constructing affiliations for {}: {} {}'
                      .format(self.doi,
                              contrib_dict.get('given_names'),
                              contrib_dict.get('surname')))
                contrib_dict['affiliations'] = [""]
            try:
                contrib_dict['footnotes'] = [aff_dict.get(aff, "")
                                             for k, v in contrib_dict['rid_dict'].items()
                                             for aff in v
                                             if k == 'fn'
                                             ]
            except AttributeError:
                print('error constructing footnote matches for {}: {} {}'
                      .format(self.doi,
                              contrib_dict.get('given_names'),
                              contrib_dict.get('surname')))
                contrib_dict['affiliations'] = [""]
            # make list of all contribs
            contrib_dict_list.append(contrib_dict)

        # match authors to credit_dicts (from author notes) if necessary
        if credit_dict:
            author_list = [author for author in contrib_dict_list
                           if author.get('contrib_type', None) == 'author']
            author_list, credit_matching_error = match_contribs_to_dicts(author_list,
                                                                         credit_dict,
                                                                         contrib_key='author_roles')
            for author in author_list:
                role_list = author.get('author_roles', None)
                author['author_roles'] = {'author_notes': role_list}

            if credit_matching_error:
                print('Warning: authors not matched correctly to author_roles for {}'
                      .format(self.doi))

        # match corresponding authors to email addresses
        corr_author_list = [contrib for contrib in contrib_dict_list if contrib.get('author_type', None) == 'corresponding']
        if not corr_author_list and email_dict:
            print('Email but no corresponding author found for {}'.format(self.doi))
            # matching_error = True
        if corr_author_list and not email_dict:
            print('Corr emails not found for {}'.format(self.doi))
            matching_error = True
        if len(corr_author_list) == 1:
            corr_author = corr_author_list[0]
            try:
                corr_author['email'] = email_dict[corr_author['rid_dict']['corresp'][0]]
            except KeyError:
                if len(email_dict) == 1:
                    corr_author['email'] = list(email_dict.values())[0]
                else:
                    print('one_corr_author error finding email for {} in {}'.format(corr_author, email_dict))
                    matching_error = True
        elif email_dict and len(corr_author_list) > 1 and len(set([tuple(x) for x in email_dict.values()])) > 1:
            corr_author_list, matching_error = match_contribs_to_dicts(corr_author_list,
                                                                       email_dict,
                                                                       contrib_key='email')
        elif len(corr_author_list) > 1:
            if email_dict and (len(email_dict) == 1 or len(set([tuple(x) for x in email_dict.values()])) == 1):
                # if there's only one email address, use it for all corr authors
                for corr_author in corr_author_list:
                    corr_author['email'] = list(email_dict.values())[0]
            else:
                matching_error = True
        else:
            corr_author_list = []

        match_error_printed = False
        if email_dict and len(email_dict) > len(corr_author_list) > 0:
                print('Contributing author email included for {}'
                      .format(self.doi))
                match_error_printed = True
        elif email_dict and 1 < len(email_dict) < len(corr_author_list):
            print('{} corresponding author email(s) missing for {}'
                  .format(len(corr_author_list) - len(email_dict), self.doi))
            match_error_printed = True

        if matching_error and email_dict and not match_error_printed:
            print('Warning: corresponding authors not matched correctly to email addresses for {}'
                  .format(self.doi))
        return contrib_dict_list

    def get_related_dois(self):
        """For a given article, get the list of DOIs of related PLOS articles.
        Creates a dictionary of related dois & their type from the <related-articles> xpath location
        Use primarily to map amendment notifications to articles that have been amended
        :return: dictionary of related DOIs
        :rtype: dict
        """
        related_article_elements = self.get_element_xpath(tag_path_elements=["/",
                                                                             "article",
                                                                             "front",
                                                                             "article-meta",
                                                                             "related-article"])
        related_article_dict = {}

        if related_article_elements:
            for elem in related_article_elements:
                related_doi = elem.attrib
                related_article = related_doi['{http://www.w3.org/1999/xlink}href']
                related_article = related_article.lstrip('info:doi/')
                if not related_article_dict.get(elem.attrib['related-article-type'], None):
                    # begin building the list of DOIs with that related-article-type
                    related_article_dict[elem.attrib['related-article-type']] = [related_article]
                else:
                    # there is more than one article with the same related-article-type
                    related_article_dict[elem.attrib['related-article-type']].append(related_article)
        else:
            # no related articles exist
            pass
        return related_article_dict

    def check_if_link_works(self):
        """See if a link is valid (i.e., returns a '200' to the HTML request).

        Used for checking a URL to a PLOS article's landing page or XML file on journals.plos.org
        Full list of potential status codes: https://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
        :return: boolean if HTTP status code returned available or unavailable,
        "error" if a different status code is returned than 200 or 404
        """
        request = requests.get(self.url)
        if request.status_code == 200:
            return True
        elif request.status_code == 404:
            return False
        else:
            return 'error'

    def check_if_doi_resolves(self, plos_valid=True):
        """Whether a PLOS DOI resolves via dx.doi.org to the correct article landing page.

        If the link works, make sure that it points to the same DOI
        Checks first if it's a valid DOI or see if it's a redirect.
        :return: 'works' if works as expected, 'doesn't work' if it doesn't resolve correctly,
        or if the metadata DOI doesn't match self.doi, return the metadata DOI
        """
        if plos_valid and validate_doi(self.doi) is False:
            return "Not valid PLOS DOI structure"
        url = "http://dx.doi.org/" + self.doi
        if self.check_if_link_works() is True:
            headers = {"accept": "application/vnd.citationstyles.csl+json"}
            r = requests.get(url, headers=headers)
            r_doi = r.json()['DOI']
            if r_doi == self.doi:
                return "works"
            else:
                return r_doi
        else:
            return "doesn't work"

    @property
    def xml(self):
        """Returns string from local xml file.
        """
        local_xml = et.tostring(self.tree,
                                method='xml',
                                encoding='unicode')
        return local_xml

    @property
    def tree(self):
        """The element tree object created from an article's local XML file

        See http://lxml.de/api/lxml.etree._ElementTree-class.html
        After accessing tree for the first time, it stores as an attribute
        :returns: article's element tree
        :rtype: {lxml.etree._ElementTree-class} or None
        """
        if self._tree is None:
            if self.local:
                local_element_tree = et.parse(self.filename)
                self._tree = local_element_tree
            else:
                print("Local article file not found: {}".format(self.filename))
                return None
        else:
            pass
        return self._tree

    @property
    def root(self):
        """Get the root (base) element of an article.
        """
        return self.tree.getroot()

    def get_page(self, page_type='article'):
        """Get any of the PLOS URLs associated with a particular DOI.

        Based on `get_page_base()`, which customizes the beginning URL by journal.
        :param page_type: one of the keys in `plos_page_dict`, defaults to article
        """
        BASE_LANDING_PAGE = _get_base_page(self.journal)
        try:
            page = BASE_LANDING_PAGE + LANDING_PAGE_SUFFIX.format(plos_page_dict[page_type],
                                                                  self.doi)
            if page_type == 'assetXMLFile':
                page += URL_SUFFIX
        except KeyError:
            raise Exception('Invalid page_type; value must be one of the following: {}'.format(list(plos_page_dict.keys())))
        return page

    @property
    def page(self):
        """ The URL of the landing page for an article.

        Where to access an article's HTML version
        """
        return self.get_page()

    @property
    def url(self):
        """The direct url of an article's XML file.
        """
        return self.get_page(page_type='assetXMLFile')

    @property
    def taxonomy(self):
        """Taxonomy information. For a complete list of subject areas see
        https://github.com/PLOS/plos-thesaurus
        """
        tag_path_elements = ('/',
                             'article',
                             'front',
                             'article-meta',
                             'article-categories')
        e_list = self.get_element_xpath(tag_path_elements=tag_path_elements)
        subjs_dict = {}
        for subj in e_list[0].getchildren():
            try:
                sbjindex = subj.values()[0].strip()
                if sbjindex in subjs_dict:
                    subjs_dict[sbjindex].append(tuple(e.text for e in subj.iter('subject')))
                else:
                    subjs_dict[sbjindex] = [tuple(e.text for e in subj.iter('subject'))]
            except IndexError:
                if 'No subject' in subjs_dict:
                    subjs_dict['No subject'].append(tuple(e.text for e in
                                                 subj.iter('subject')))
                else:
                    subjs_dict['No subject'] = [tuple(e.text for e in
                                                 subj.iter('subject'))]
        return subjs_dict

    @property
    def filename(self):
        """The path on the local file system to a given article's XML file
        """
        if 'annotation' in self.doi:
            article_path = os.path.join(self.directory, 'plos.correction.' + self.doi.split('/')[-1] + '.xml')
        else:
            article_path = os.path.join(self.directory, self.doi.lstrip('10.1371/') + '.xml')
        return article_path

    @property
    def local(self):
        """Boolean of whether the article is stored locally or not.

        Stored as attribute after first access
        """
        if self._local is None:
            self._local = os.path.isfile(self.filename)
        else:
            pass
        return self._local

    @property
    def proof(self):
        """
        For a single article in a directory, check whether it is an 'uncorrected proof' or a
        'VOR update' to the uncorrected proof, or neither.
        :return: proof status if it exists
        :rtype: str
        """
        xpath_results = self.get_element_xpath()
        proof = ''
        for result in xpath_results:
            if result.text == 'uncorrected-proof':
                proof = 'uncorrected_proof'
            elif result.text == 'vor-update-to-uncorrected-proof':
                proof = 'vor_update'
        return proof

    @property
    def remote_proof(self):
        """
        For a single article online, check whether it is an 'uncorrected proof' or a
        'VOR update' to the uncorrected proof, or neither.
        :return: proof status if it exists; otherwise, None
        """
        xpath_results = self.get_element_xpath(remote=True)
        proof = ''
        for result in xpath_results:
            if result.text == 'uncorrected-proof':
                proof = 'uncorrected_proof'
            elif result.text == 'vor-update-to-uncorrected-proof':
                proof = 'vor_update'
        return proof

    @property
    def remote_tree(self):
        """Gets the lxml element tree of an article from its remote URL.

        Can compare local (self.xml) to remote versions of XML
        :returns: article's online element tree
        :rtype: {lxml.etree._ElementTree-class}
        """
        return et.parse(self.url)

    @property
    def journal(self):
        """Journal that an article was published in.
        Can be PLOS Biology, Medicine, Neglected Tropical Diseases, Pathogens,
        Genetics, Computational Biology, ONE, or the now defunct Clinical Trials.
        Relies on a simple doi_to_journal transform when possible, and uses `Journal().parse_plos_journal()`
        for the "annotation" DOIs that don't have that journal information in the DOI.
        """
        if 'annotation' not in self.doi:
            journal = Journal.doi_to_journal(self.doi)
        else:
            journal_meta = self.root.xpath('/article/front/journal-meta')[0]
            journal = str(Journal(journal_meta))
        return journal

    @property
    def title(self):
        """For an individual PLOS article, get its title.

        :return: string of article title at specified xpath location
        """
        title = self.get_element_xpath(tag_path_elements=["/",
                                                          "article",
                                                          "front",
                                                          "article-meta",
                                                          "title-group",
                                                          "article-title"])
        title_text = et.tostring(title[0], encoding='unicode', method='text', pretty_print=True)
        title_cleaned = " ".join(title_text.split())
        return title_cleaned

    @property
    def rich_title(self):
        """For an individual PLOS article, get its title with HTML formatting.

        Preserves HTML formatting but removes all other XML tagging, namespace/xlink info, etc.
        Doesn't do xpath directly on `self.root` so can deannotate separate object
        See http://lxml.de/objectify.html#how-data-types-are-matched for more info on deannotate process
        Exceptions that still need handling:
        10.1371/journal.pone.0179720, 10.1371/journal.pone.0068479, 10.1371/journal.pone.0069681,
        10.1371/journal.pone.0068965, 10.1371/journal.pone.0083868, 10.1371/journal.pone.0069554,
        10.1371/journal.pone.0068324, 10.1371/journal.pone.0067986, 10.1371/journal.pone.0068704,
        10.1371/journal.pone.0068492, 10.1371/journal.pone.0068764, 10.1371/journal.pone.0068979,
        10.1371/journal.pone.0068544, 10.1371/journal.pone.0069084, 10.1371/journal.pone.0069675

        :return: string of article title at specified xpath location
        """
        root = self.root
        objectify.deannotate(root, cleanup_namespaces=True, xsi_nil=True)
        art_title = root.xpath("/article/front/article-meta/title-group/article-title")
        art_title = art_title[0]
        try:
            text = art_title.text
            if text is None:
                text = ''
            text += ''.join(et.tostring(child, encoding='unicode') if child.tag not in ('ext-link', 'named-content', 'sc', 'monospace') \
                                                                   else child.text + child.tail if child.tail is not None \
                                                                   else child.text
                            for child in art_title.getchildren())
            title = text.replace(' xmlns:xlink="http://www.w3.org/1999/xlink"', '') \
                        .replace(' xmlns:mml="http://www.w3.org/1998/Math/MathML"', '') \
                        .replace(' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance', '')
        except TypeError:
            # try to rewrite so this isn't needed
            print('Error processing article title for {}'.format(self.doi))
            title = et.tostring(art_title, method='text', encoding='unicode')
        return title

    @property
    def pubdate(self):
        """The date an article was published online.

        :returns: article publication date
        :rtype: {datetime.datetime}
        """
        dates = self.get_dates()
        return dates['epub']

    @property
    def revdate(self):
        """The date an article's version-of-record (`proof(self)` == 'vor_update') was published online.

        :returns: article revision date
        :rtype: {datetime.datetime}
        """
        dates = self.get_dates()
        return dates['updated']

    @property
    def license(self):
        """Return dictionary of CC license information from the license field."""
        permissions = self.root.xpath('/article/front/article-meta/permissions')[0]
        return dict(License(permissions, self.doi))

    @property
    def contributors(self):
        """ List of contributors to an article.

        Including authors and editors
        Stores as attribute after first access
        :returns: list of dictionaries for each contributor
        :rtype: {list}
        """
        if self._contributors is None:
            self._contributors = self.get_contributors_info()
        else:
            pass
        return self._contributors

    @property
    def authors(self):
        """List of authors of an article. Including contributing and corresponding.

        For more about authorship criteria, see http://journals.plos.org/plosone/s/authorship
        """
        contributors = self.contributors
        return [contrib for contrib in contributors if contrib.get('contrib_type', None) == 'author']

    @property
    def corr_author(self):
        """List of corresponding authors of an article.
        """
        contributors = self.contributors
        return [contrib for contrib in contributors if contrib.get('author_type', None) == 'corresponding']

    @property
    def editor(self):
        """The editor on the article.

        For more about the editorial process, see http://journals.plos.org/plosone/s/editorial-and-peer-review-process
        """
        contributors = self.contributors
        return [contrib for contrib in contributors if contrib.get('contrib_type', None) == 'editor']

    @property
    def emails(self):
        """List of emails of corresponding author(s).
        Unlike get_corr_author_emails() dict, it does not differentiate by author.
        Joins multiple emails into a single list.
        :return: list of corresponding author email addresses
        """
        email_dict = self.get_corr_author_emails()
        email_list = []
        for k, v in email_dict.items():
            email_list.extend(v)
        return email_list

    def emails_to_string(self):
        """Produces string of emails of corresponding author(s).
        Joins multiple emails into a single string, separated by semi-colons.
        Used for exporting to .csv
        :return: string of corresponding author email addresses
        """
        return '; '.join(self.emails)

    @property
    def type_(self):
        """For an article file, get its JATS article type.

        Used primarily to find Correction (and thereby corrected) articles
        :return: JATS article_type at that xpath location
        """
        type_element_list = self.get_element_xpath(tag_path_elements=["/",
                                                                      "article"])
        return type_element_list[0].attrib['article-type']

    @property
    def plostype(self):
        """For an article file, get its PLOS article type.

        This format is less standardized than the JATS article type (self.type_)
        :return: PLOS article_type at that xpath location
        """
        article_categories = self.get_element_xpath(tag_path_elements=["/",
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
                    plos_article_type = s
        return plos_article_type

    @property
    def dtd(self):
        """Document Type Definition for an article.
        For more information on these DTD tagsets, see https://jats.nlm.nih.gov/1.1d3/ and https://dtd.nlm.nih.gov/3.0/
        """
        dtd = self.get_element_xpath(tag_path_elements=["/",
                                                        "article"])
        try:
            dtd = dtd[0].attrib['dtd-version']
            if str(dtd) == '3.0':
                dtd = 'NLM 3.0'
            elif dtd == '1.1d3':
                dtd = 'JATS 1.1d3'
        except KeyError:
            print('Error parsing DTD from', self.doi)
            dtd = 'N/A'
        return dtd

    @property
    def abstract(self):
        """For an individual PLOS article, get the string of the abstract content.

        PLOS articles can have multiple abstract fields at the same XPath location,
        however the actual abstract is distinguished by having no attributes (`[count(@*)=0]`).
        Info about the article abstract: http://journals.plos.org/plosone/s/submission-guidelines#loc-abstract
        :return: plain-text string of content in abstract
        """
        abstract_list = self.get_element_xpath(tag_path_elements=["/",
                                                                  "article",
                                                                  "front",
                                                                  "article-meta",
                                                                  "abstract[count(@*)=0]"])
        if abstract_list:
                abstract = abstract_list[0]
                assert len(abstract_list) == 1

                abstract_text = et.tostring(abstract[0], encoding='unicode', method='text')
        else:
            if self.type_ == 'research-article' and self.plostype == 'Research Article':
                print('No abstract found for research article {}'.format(self.doi))

            abstract_text = ''

        # clean up text: rem white space, new line marks, blank lines
        abstract_text = abstract_text.strip().replace('  ', '')
        abstract_text = os.linesep.join([s for s in abstract_text.splitlines() if s])

        return abstract_text

    @property
    def amendment(self):
        """Whether the JATS article type is a correction, retraction, or expression of concern.

        These are the three article types ('amendments') that potentially warrant a change in the original article
        that they reference (i.e., the 'related-doi'.)
        See https://jats.nlm.nih.gov/archiving/tag-library/1.1/attribute/article-type.html
        :returns: True if an amendment article type, False if not
        :rtype: {bool}
        """
        if self.type_ in ['correction', 'retraction', 'expression-of-concern']:
            return True
        else:
            return False

    @property
    def related_dois(self):
        """PLOS DOIs related to current article.

        Compresses the values of `self.get_related_dois()` dictionary into a single list of DOI strings
        More strict for which keys to include for corrections, retractions, and expressions of concern, the three
        amendment article types.
        :returns: list of related DOIs
        :rtype: list
        """
        doi_list = []
        related_doi_dict = self.get_related_dois()
        if self.amendment:
            # only use certain keys if an amendment article
            if self.type_ == 'correction':
                attrib_name = 'corrected-article'
            elif self.type_ == 'retraction':
                attrib_name = 'retracted-article'
            elif self.type_ == 'expression-of-concern':
                attrib_name = 'object-of-concern'
            for k, v in related_doi_dict.items():
                if k == attrib_name:
                    doi_list = v
                    break
            if not doi_list:
                doi_list = [v for v in related_doi_dict.values()]
                print('{} has incorrect related_doi field attribute'.format(self.doi))

        else:
            # flatten all dict values if not an amendment article
            if related_doi_dict:
                for k, v in related_doi_dict.items():
                    doi_list.extend(v)

        return doi_list

    @property
    def correction(self):
        """Get the DOIs of all corrections type articles that correct the current article.

        Some PLOS articles include a 'correction-forward' related-article-type, meaning
        an article that has been issued a correction is linked to its correcting article(s).
        Only for the SIX PLOS journals (i.e. not on PLOS ONE).
        Usually there is only one DOI, unless the article has been issued multiple corrections.
        :return: DOIs of the correction articles
        :rtype: list
        """
        correction_doi = ''
        related_dois = self.get_related_dois()
        for k, v in related_dois.items():
            if k == 'correction-forward':
                correction_doi = v
                break
        return correction_doi

    @property
    def counts(self):
        """For a single article, return a dictionary of the several counts functions that are available.

        Dictionary format for XML tags: {figures: fig-count, pages: page-count, tables: table-count}
        For articles without the figure and table counts fields, calculates those values using XPath.
        :return: counts dictionary of number of figures, pages, and tables in the article
        """
        counts = {}

        tag_path = ["/",
                    "article",
                    "front",
                    "article-meta",
                    "counts"]
        count_element_list = self.get_element_xpath(tag_path_elements=tag_path)
        for count_element in count_element_list:
            for count_item in count_element:
                count = count_item.get('count')
                count_type = count_item.tag
                counts[count_type] = int(count)
        if len(counts) > 3:  # this shouldn't happen
            print(counts)
        if 'fig-count' not in counts:
            counts['fig-count'] = len(self.root.xpath('.//fig'))
        if 'table-count' not in counts:
            counts['table-count'] = len(self.root.xpath('.//table-wrap'))
        return counts

    @property
    def word_count(self):
        """For an article, get how many words are in the body.

        :return: count of words in the body of the PLOS article
        """
        body_element = self.get_element_xpath(tag_path_elements=["/",
                                                                 "article",
                                                                 "body"])
        try:
            body_text = et.tostring(body_element[0], encoding='unicode', method='text')
            body_word_count = len(body_text.split(" "))
        except IndexError:
            print("Error parsing article body: {}".format(self.doi))
            body_word_count = 0
        return body_word_count

    @filename.setter
    def filename(self, value):
        """Sets an article object using a local filename.

        Converts a filename to DOI using an existing function.
        :param value: filename
        :type value: string
        """
        self.doi = filename_to_doi(value)

    @classmethod
    def from_filename(cls, filename):
        """Initiate an article object using a local XML file.

        Will set `self.directory` if the full file path is available. If not, it will
        default to `get_corpus_dir()` via `Article().__init__`. This method is most useful
        for instantiating an Article object when the file is not in the default corpus
        directory, or when changing directories.
        """
        if os.path.isfile(filename):
            directory = os.path.dirname(filename)
        else:
            directory = None
        return cls(filename_to_doi(filename), directory=directory)
