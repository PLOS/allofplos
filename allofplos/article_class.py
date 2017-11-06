import os
import re
import subprocess

import lxml.etree as et


from transformations import (filename_to_doi, EXT_URL_TMP, INT_URL_TMP,
                             BASE_URL_ARTICLE_LANDING_PAGE)
from plos_regex import (validate_doi, corpusdir)
from article_elements import (parse_article_date, get_rid_dict, get_contrib_name,
                              get_contrib_ids, get_credit_taxonomy,
                              match_contrib_initials_to_dict, get_contrib_info,
                              match_author_names_to_emails, match_contribs_to_dicts)


class Article(object):
    plos_prefix = ''

    def __init__(self, doi, directory=None):
        self.doi = doi
        if directory is None:
            self.directory = corpusdir
        else:
            self.directory = directory
        self.reset_memoized_attrs()
        self._editor = None

    def reset_memoized_attrs(self):
        self._tree = None
        self._local = None
        self._correct_or_retract = None  # Will probably need to be an article subclass

    @property
    def doi(self):
        return self._doi

    @property
    def text_editor(self):
        try:
            return self._text_editor
        except AttributeError as e:
            print(("{}:\n"
                   "You need to assign a non-terminal texteditor "
                   "command to self.text_editor").format(e))

    @text_editor.setter
    def text_editor(self, value):
        self._text_editor = value

    @doi.setter
    def doi(self, d):
        if validate_doi(d) is False:
            raise Exception("Invalid format for PLOS DOI")
        self.reset_memoized_attrs()
        self._doi = d

    def get_local_xml(self, pretty_print=True):
        local_xml = et.tostring(self.tree,
                                method='xml',
                                encoding='unicode',
                                pretty_print=pretty_print)
        return print(local_xml)

    def get_url(self, plos_network=False):
        URL_TMP = INT_URL_TMP if plos_network else EXT_URL_TMP
        return URL_TMP.format(self.doi)

    def get_remote_xml(self, pretty_print=True):
        remote_xml = et.tostring(self.remote_element_tree,
                                 method='xml',
                                 encoding='unicode',
                                 pretty_print=pretty_print)
        return print(remote_xml)

    def open_in_editor(self, text_editor=None):

        if not (text_editor or self.text_editor):
            raise TypeError("You have not specified an text_editor. Please do so.")

        subprocess.call([self._text_editor, self.filename])

    def open_in_browser(self):
        subprocess.call(["open", self.page])

    def get_element_xpath(self, tag_path_elements=None):
        """
        For a local article's root element, grab particular sub-elements via XPath location
        Defaults to reading the element location for uncorrected proofs/versions of record
        :param article_root: the xml file for a single article
        :param tag_path_elements: xpath location in the XML tree of the article file
        :return: list of elements with that xpath location
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
        """
        For an individual PLOS article, get the journal it was published in.
        :param caps_fixed: whether to render 'PLOS' in the journal name correctly or as-is ('PLoS')
        :return: PLOS journal at specified xpath location
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
        """
        For an individual article, get all of its dates, including publication date (pubdate), submission date
        :return: dict of date types mapped to datetime objects for that article
        """
        dates = {}

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

        Used to map individual contributors to their institutions
        :returns: Dictionary of footnote ids to institution information
        :rtype: {[dict]}
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
                            aff_text_fixed = ' '.join([aff_string.strip() for aff_string in sub_el.text.splitlines()])
                            aff_dict[el.attrib['id']] = aff_text_fixed
                else:
                    # the address for some affiliations is not wrapped in an addr-line tag
                    aff_dict[el.attrib['id']] = el.text.replace('\n', '').replace('\r', '').replace('\t', '')
        return aff_dict

    def get_fn_dict(self):
        """For a given PLOS article, get list of contributor-affiliated institutions.

        Used to map individual contributors to their institutions
        :returns: Dictionary of footnote ids to institution information
        :rtype: {[dict]}
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
                    # the address for some affiliations is not wrapped in an addr-line tag
                    fn_dict[el.attrib['id']] = el.text.replace('\n','').replace('\r','').replace('\t','')
        return fn_dict

    def get_corr_author_emails(self):
        tag_path = ["/",
                    "article",
                    "front",
                    "article-meta",
                    "author-notes"]
        author_notes_element = self.get_element_xpath(tag_path_elements=tag_path)[0]
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
                                print('Error handling multiple email addresses for {} in {}'.format(et.tostring(item), self.doi))
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
        contribution types by author initials.
        Works for highly formatted lists with subelements (e.g. '10.1371/journal.pone.0170354') and structured single strings
        (e.g. '10.1371/journal.pone.0050782'), but still fails for unusual strings (e.g, '10.1371/journal.pntd.0000072')
        TODO: Use regex to properly separate author roles from initials for unusual strings.
        """
        if self.type_ in ['correction', 'retraction', 'expression-of-concern']:
            return {}
        tag_path = ["/",
                    "article",
                    "front",
                    "article-meta",
                    "author-notes"]
        author_notes_element = self.get_element_xpath(tag_path_elements=tag_path)[0]
        author_contributions = {}
        contrib_dict = {}
        initials_list = []
        for note in author_notes_element:
            if note.attrib.get('fn-type', None) == 'con':
                try:
                    con_element = note[0][0]
                    con_list = con_element.getchildren()
                    for con_item in con_list:
                        contribution = con_item[0][0].text.rstrip(':')
                        contributor_initials = (con_item[0][0].tail.lstrip(' ').rstrip('.')).split(' ')
                        initials_list.extend(contributor_initials)
                        contrib_dict[contribution] = contributor_initials
                except IndexError:
                    contributions = note[0].text
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
            # initialize contrib dict
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
                print('error constructing affiliations for {}: {} {}'.format(self.doi, contrib_dict.get('given_names'), contrib_dict.get('surname')))
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
        if self.type_ == 'correction' or self.type_ == 'retraction':
            self._correct_or_retract = True
        else:
            self._correct_or_retract = False
        return self._correct_or_retract

    def get_related_doi(self):
        """
        For an article file, get the DOI of the first related article
        More strict in tag search if article is correction type
        Use primarily to map correction and retraction notifications to articles that have been corrected
        NOTE: what to do if more than one related article?
        :return: doi at that xpath location
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
            related_article_element = related_article_elements[0].attrib
            related_article = related_article_element['{http://www.w3.org/1999/xlink}href']
            related_article = related_article.lstrip('info:doi/')
        return related_article

    def get_counts(self):
        """
        For a single article, return a dictionary of the several counts functions that are available
        (figures: fig-count, pages: page-count, tables: table-count)
        :return: counts dictionary
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
        """
        For an article, get how many words are in the body
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

    @property
    def xml(self):
        return self.get_local_xml()

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
