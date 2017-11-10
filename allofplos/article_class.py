import os
import re
import subprocess

import lxml.etree as et
import requests

from transformations import (filename_to_doi, EXT_URL_TMP, INT_URL_TMP,
                             BASE_URL_ARTICLE_LANDING_PAGE)
from plos_regex import (validate_doi, corpusdir)
from article_elements import (parse_article_date, get_rid_dict,
                              get_contrib_info, match_contribs_to_dicts)


class Article():
    """The primary object of a PLOS article, instantiated by a valid PLOS DOI.
    """
    def __init__(self, doi, directory=None, plos_network=False):
        self.doi = doi
        if directory is None:
            self.directory = corpusdir
        else:
            self.directory = directory
        self.reset_memoized_attrs()
        self.plos_network = plos_network
        self._editor = None

    def reset_memoized_attrs(self):
        """Reset attributes to None when instantiating a new article object
        
        For article attributes that are memoized and specific to that particular article
        (including the XML tree and whether the xml file is in the local directory),
        reset them when creating a new article object.
        """
        self._tree = None
        self._local = None
        self._correct_or_retract = None  # Will probably need to be an article subclass

    @property
    def doi(self):
        """The unique Digital Object Identifier for a PLOS article.
        
        See https://www.doi.org/
        :returns: DOI of the article object
        :rtype: {str}
        """
        return self._doi

    @property
    def text_editor(self):
        """Your text editor of choice that can be called from the command line.
        Persists across article objects.
        Use with self.open_in_editor() to open an article of interest.
        Check your text editor's documentation to learn how to launch it from the command line.
        For Sublime Text, see http://docs.sublimetext.info/en/latest/command_line/command_line.html
        :returns: command line shortcut for the text editor
        :rtype: {str}
        """
        try:
            return self._text_editor
        except AttributeError as e:
            print(("{}:\n"
                   "You need to assign a non-terminal texteditor "
                   "command to self.text_editor").format(e))

    @text_editor.setter
    def text_editor(self, value):
        """Sets the text editor for all article objects
        :param value: from self.text_editor
        :type value: {str}
        """
        self._text_editor = value

    @doi.setter
    def doi(self, d):
        """
        Using regular expressions, make sure the doi is valid before
        instantiating the article object.
        """
        if validate_doi(d) is False:
            raise Exception("Invalid format for PLOS DOI")
        self.reset_memoized_attrs()
        self._doi = d

    def __str__(self, pretty_print=True):
        """Output when you print an article object on the command line

        For parsing and viewing the XML of a local article. Should not be used for hashing
        :param pretty_print: Includes indenting/whitespace, defaults to True
        :type pretty_print: bool, optional
        """
        local_xml = et.tostring(self.tree,
                                method='xml',
                                encoding='unicode',
                                pretty_print=pretty_print)
        print(local_xml)

    def __repr__(self):
        """Value of an article object when you call it directly on the command line.

        Shows the DOI and title of the article
        :returns: DOI and title
        :rtype: {str}
        """
        out = "DOI: {0}\nTitle: {1}".format(self.doi, self.title)
        return out

    def get_url(self, plos_network=False):
        """The PLOS external URL for the XML of a particular article.

        Used for downloading articles, and comparing local XML to remote XML
        :param plos_network: whether inside the PLOS network, defaults to False
        :type plos_network: bool, optional
        :returns: direct URL to the article XML file
        :rtype: {str}
        """
        URL_TMP = INT_URL_TMP if plos_network else EXT_URL_TMP
        return URL_TMP.format(self.doi)

    def get_remote_xml(self):
        """For an article, parse its XML file at the location of self.url

        Uses the lxml element tree to create the string, which is saved to a local
        file when downloaded
        :returns: string of entire remote article file
        :rtype: {str}
        """
        remote_xml = et.tostring(self.remote_element_tree,
                                 method='xml',
                                 encoding='unicode')
        return remote_xml

    def open_in_editor(self, text_editor=None):
        """Open a local article file of interest in an external text editor.

        :param text_editor: set via self.text_editor, defaults to None
        :type text_editor: str, optional
        :raises: TypeError
        """
        if not (text_editor or self.text_editor):
            raise TypeError("You have not specified an text_editor. Please do so.")

        subprocess.call([self._text_editor, self.filename])

    def open_in_browser(self):
        """Opens the landing page (HTML) of an article in default browser.

        This is also the URL that the DOI resolves to
        """
        subprocess.call(["open", self.page])

    def get_element_xpath(self, tag_path_elements=None):
        """For a local article's root element, grab particular sub-elements via XPath location.

        Defaults to reading the element location for uncorrected proofs/versions of record
        The basis of every method and property looking for particular metadata fields
        :param article_root: the xml file for a single article
        :param tag_path_elements: xpath location in the XML tree of the article file
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
        return self.root.xpath(tag_location)

    def get_plos_journal(self, caps_fixed=True):
        """For an individual PLOS article, get the journal it was published in.

        :param caps_fixed: whether to render 'PLOS' in the journal name correctly, or as-is ('PLoS')
        :return: PLOS journal name at specified xpath location
        """
        try:
            journal = self.get_element_xpath(tag_path_elements=["/",
                                                                "article",
                                                                "front",
                                                                "journal-meta",
                                                                "journal-title-group",
                                                                "journal-title"])
            journal = journal[0].text
        except IndexError:
            # Need to file JIRA ticket: only affects pone.0047704
            journal_meta = self.get_element_xpath(tag_path_elements=["/",
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

    def get_dates(self, string_=False, string_format='%Y-%m-%d', debug=False):
        """For an individual article, get all of its dates, including publication date (pubdate), submission date.

        Defaults to datetime objects
        :param string_: whether to return dates as a dictionary of strings
        :param string_format: if string_ is True, the format to return the dates in
        :param debug: whether to check that the dates are in the correct order, defaults to False
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
        if debug:
            # check whether date received is before date accepted is before pubdate
            if dates.get('received', '') and dates.get('accepted', '') in dates:
                if not dates['received'] <= dates['accepted'] <= dates['epub']:
                    print('{}: dates in wrong order'.format(self.doi))

        if string_:
            # can return dates as strings instead of datetime objects if desired
            for key, value in dates.items():
                if value:
                    dates[key] = value.strftime(string_format)

        return dates

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
                        fn_dict[el.attrib['id']] = sub_el.text
                else:
                    # in case is at top-level of element
                    fn_dict[el.attrib['id']] = el.text.replace('\n', '').replace('\r', '').replace('\t', '')
        return fn_dict

    def get_corr_author_emails(self):
        """For an article, grab the email addresses of the corresponding authors.
        The email addresses are in an element of author notes. While most articles have one corresponding
        author with one email address, sometimes there are 1) multiple authors, and/or 2) multiple emails per
        author. In the first case, author initials are used in the text to separate emails. In the second case,
        a comma is used to separate emails. Initials are how emails can be matched to multiple
        authors. See also `match_author_names_to_emails()` for the back-up method of name matching.
        :return: dictionary of rid or author initials mapped to list of email address(es)
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
            return None
        corr_emails = {}
        email_list = []
        for note in author_notes_element:
            if note.tag == 'corresp':
                author_info = note.getchildren()
                for i, item in enumerate(author_info):

                    # if no author initials (one corr author)
                    if item.tag == 'email' and item.tail is None and item.text:
                        email_list.append(item.text)
                        if item.text == '':
                            print('No email available for {}'.format(self.doi))
                        corr_emails[note.attrib['id']] = email_list

                    # if more than one email per author
                    elif item.tag == 'email' and ',' in item.tail:
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
            return None
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
                        contribution = con_item[0][0].text.rstrip(':')
                        contributor_initials = (con_item[0][0].tail.lstrip(' ').rstrip('.')).split(' ')
                        initials_list.extend(contributor_initials)
                        contrib_dict[contribution] = contributor_initials
                except IndexError:
                    # for single strings, though it doesn't parse all of them correctly.
                    # Example: '10.1371/journal.pone.0050782'
                    contributions = note[0].text
                    if contributions is None:
                        print('Error parsing {}: {}'.format(self.doi, et.tostring(con_element)))
                        return None
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
        """Get and organize information about each article's contributor.
        This includes both authors and editors of the article.
        This function both creates article-level dictionaries of contributor information,
        as well as parses individual <contrib> elements. It reconciles the dicts together
        using a number of external functions from article_elements.py
        :returns: dictionary of metadata for each <contrib> element
        :rtype: list of dicts
        """

        # TODO: param to remove unnecessary fields (initials) and dicts (rid_dict)
        # TODO: also get funding information, data availability, etc

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
                print('Error getting contrib info for {}'.format(self.doi, self.type_))

            # get dictionary of contributor's footnote types to footnote ids
            contrib_dict['rid_dict'] = get_rid_dict(contrib)

            # map affiliation footnote ids to the actual institutions
            try:
                contrib_dict['affiliations'] = [aff_dict.get(aff, "")
                                                for k, v in contrib_dict['rid_dict'].items()
                                                for aff in v
                                                if k == 'aff'
                                                ]
            except TypeError:
                print('error constructing affiliations for {}: {} {}'
                      .format(self.doi,
                              contrib_dict.get('given_names'),
                              contrib_dict.get('surname')))
                contrib_dict['affiliations'] = [""]

            contrib_dict['footnotes'] = [aff_dict.get(aff, "")
                                         for k, v in contrib_dict['rid_dict'].items()
                                         for aff in v
                                         if k == 'fn'
                                         ]

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
            print('Corr authors but no emails found for {}'.format(self.doi))
            matching_error = True
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
                    # print('one_corr_author error finding email for {} in {}'.format(corr_author, email_dict))
                    matching_error = True
        elif len(corr_author_list) > 1:
            corr_author_list, matching_error = match_contribs_to_dicts(corr_author_list,
                                                                       email_dict,
                                                                       contrib_key='email')
        else:
            corr_author_list = []

        if matching_error:
            print('Warning: corresponding authors not matched correctly to email addresses for {}'
                  .format(self.doi))
        return contrib_dict_list

    def correct_or_retract_bool(self):
        """Whether the JATS article type is a correction or retraction.

        See https://jats.nlm.nih.gov/archiving/tag-library/1.1/attribute/article-type.html
        :returns: True if a correction or retraction, false if not
        :rtype: {bool}
        """
        if self.type_ == 'correction' or self.type_ == 'retraction':
            self._correct_or_retract = True
        else:
            self._correct_or_retract = False
        return self._correct_or_retract

    def get_related_doi(self):
        """For an article file, get the DOI of the first related article.

        More strict in tag search if article is correction type
        Use primarily to map correction and retraction notifications to articles that have been corrected
        NOTE: what to do if more than one related article?
        :return: first doi at that xpath location
        """
        related_article_elements = self.get_element_xpath(tag_path_elements=["/",
                                                                             "article",
                                                                             "front",
                                                                             "article-meta",
                                                                             "related-article"])
        related_article = ''
        if self.type_ == 'correction':
            for element in related_article_elements:
                if element.attrib['related-article-type'] in ('corrected-article', 'companion'):
                    corrected_doi = element.attrib['{http://www.w3.org/1999/xlink}href']
                    related_article = corrected_doi.lstrip('info:doi/')
                    break
        else:
            try:
                related_article_element = related_article_elements[0].attrib
                related_article = related_article_element['{http://www.w3.org/1999/xlink}href']
                related_article = related_article.lstrip('info:doi/')
            except IndexError:
                return None
        return related_article

    def get_counts(self):
        """For a single article, return a dictionary of the several counts functions that are available.
        Dictionary format for XML tags: {figures: fig-count, pages: page-count, tables: table-count}
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
                counts[count_type] = count
        if len(counts) > 3:
            print(counts)
        return counts

    def get_body_word_count(self):
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
        return self.__str__()

    @property
    def tree(self):
        if self._tree is None:
            if self.local:
                local_element_tree = et.parse(self.filename)
                return local_element_tree
            else:
                print("Local article file not found: {}".format(self.filename))
                return None
        else:
            return self._tree

    @property
    def root(self):
        return self.tree.getroot()

    @property
    def page(self):
        return BASE_URL_ARTICLE_LANDING_PAGE + self.doi

    @property
    def url(self):
        return self.get_url(plos_network=self.plos_network)

    @property
    def filename(self):
        if 'annotation' in self.doi:
            article_path = os.path.join(self.directory, 'plos.correction.' + self.doi.split('/')[-1] + '.xml')
        else:
            article_path = os.path.join(self.directory, self.doi.lstrip('10.1371/') + '.xml')
        return article_path

    @property
    def local(self):
        if self._local is None:
            return os.path.isfile(self.filename)
        else:
            return self._local

    @property
    def proof(self):
        """
        For a single article in a directory, check whether it is an 'uncorrected proof' or a
        'VOR update' to the uncorrected proof, or neither
        :return: proof status if it exists; otherwise, None
        """
        xpath_results = self.get_element_xpath()
        for result in xpath_results:
            if result.text == 'uncorrected-proof':
                return 'uncorrected_proof'
            elif result.text == 'vor-update-to-uncorrected-proof':
                return 'vor_update'
            else:
                pass
        return None

    @property
    def remote_element_tree(self):
        return et.parse(self.url)

    @property
    def journal(self):
        return self.get_plos_journal()

    @property
    def title(self):
        """
        For an individual PLOS article, get its title.
        :return: string of article title at specified xpath location
        """
        title = self.get_element_xpath(tag_path_elements=["/",
                                                          "article",
                                                          "front",
                                                          "article-meta",
                                                          "title-group",
                                                          "article-title"])
        title_text = et.tostring(title[0], encoding='unicode', method='text', pretty_print=True)
        return title_text.rstrip('\n')

    @property
    def pubdate(self):
        dates = self.get_dates()
        return dates['epub']

    @property
    def authors(self):
        contributors = self.get_contributors_info()
        return [contrib for contrib in contributors if contrib.get('contrib_type', None) == 'author']

    @property
    def corr_author(self):
        contributors = self.get_contributors_info()
        return [contrib for contrib in contributors if contrib.get('author_type', None) == 'corresponding']

    @property
    def editor(self):
        contributors = self.get_contributors_info()
        return [contrib for contrib in contributors if contrib.get('contrib_type', None) == 'editor']

    @property
    def type_(self):
        """For an article file, get its JATS article type.
        Use primarily to find Correction (and thereby corrected) articles
        :return: JATS article_type at that xpath location
        """
        type_element_list = self.get_element_xpath(tag_path_elements=["/",
                                                                      "article"])
        return type_element_list[0].attrib['article-type']

    @property
    def plostype(self):
        """
        For an article file, get its PLOS article type. This format is less standardized than JATS article type
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
        """
        For more information on these DTD tagsets, see https://jats.nlm.nih.gov/1.1d3/ and https://dtd.nlm.nih.gov/3.0/
        """
        try:
            dtd = self.get_element_xpath(tag_path_elements=["/",
                                                            "article"])
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
        """
        For an individual article in the PLOS corpus, get the string of the abstract content.
        :return: plain-text string of content in abstract
        """
        abstract = self.get_element_xpath(tag_path_elements=["/",
                                                             "article",
                                                             "front",
                                                             "article-meta",
                                                             "abstract"])
        try:
            abstract_text = et.tostring(abstract[0], encoding='unicode', method='text')
        except IndexError:
            if self.type_ == 'research-article' and self.plostype == 'Research Article':
                print('No abstract found for research article {}'.format(self.doi))

            abstract_text = ''

        # clean up text: rem white space, new line marks, blank lines
        abstract_text = abstract_text.strip().replace('  ', '')
        abstract_text = os.linesep.join([s for s in abstract_text.splitlines() if s])

        return abstract_text

    @property
    def correct_or_retract(self):
        if self._correct_or_retract is None:
            return self.correct_or_retract_bool()
        else:
            return self._correct_or_retract

    @property
    def related_doi(self):
        if self.correct_or_retract is True:
            return self.get_related_doi()
        else:
            return None

    @property
    def counts(self):
        return self.get_counts()

    @property
    def word_count(self):
        return self.get_body_word_count()

    @filename.setter
    def filename(self, value):
        self.doi = filename_to_doi(value)

    @classmethod
    def from_filename(cls, filename):
        return cls(filename_to_doi(filename))
