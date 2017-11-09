import datetime
import os
import unittest

from article_class import Article
from plos_corpus import INT_URL_TMP, EXT_URL_TMP
from transformations import (doi_to_path, url_to_path, filename_to_doi, url_to_doi,
                             filename_to_url, doi_to_url)


suffix = '.xml'
corpusdir = 'allofplos_xml/'
example_url = 'http://journals.plos.org/plosone/article/file?id=10.1371/'\
              'journal.pbio.2001413&type=manuscript'
example_url_int = 'http://contentrepo.plos.org:8002/v1/objects/mogilefs-prod-'\
                  'repo?key=10.1371/journal.pbio.2001413.XML'
example_file = 'journal.pbio.2001413.xml'
example_doi = '10.1371/journal.pbio.2001413'
example_url2 = 'http://journals.plos.org/plosone/article/file?id=10.1371/'\
               'annotation/3155a3e9-5fbe-435c-a07a-e9a4846ec0b6&type=manuscript'
example_url2_int = 'http://contentrepo.plos.org:8002/v1/objects/mogilefs-'\
                   'prod-repo?key=10.1371/annotation/3155a3e9-5fbe-435c-a'\
                   '07a-e9a4846ec0b6.XML'
example_file2 = 'plos.correction.3155a3e9-5fbe-435c-a07a-e9a4846ec0b6.xml'
example_doi2 = '10.1371/annotation/3155a3e9-5fbe-435c-a07a-e9a4846ec0b6'
class_doi = '10.1371/journal.pone.0185809'


class TestDOIMethods(unittest.TestCase):

    def test_doi_conversions(self):
        """
        TODO: What this tests are about!
        """
        self.assertEqual(os.path.join(corpusdir, example_file), doi_to_path(example_doi), "{0} does not transform to {1}".format(example_doi, example_file))
        self.assertEqual(example_file2, doi_to_path(example_doi2, ''), "{0} does not transform to {1}".format(example_doi2, example_file2))
        self.assertEqual(example_url2, doi_to_url(example_doi2), "{0} does not transform to {1}".format(example_doi2, example_url2))
        self.assertEqual(example_url, doi_to_url(example_doi), "In doi_to_url, {0} does not transform to {1}".format(example_doi, example_url))
        self.assertEqual(example_url2_int, doi_to_url(example_doi2, plos_network=True),
                         "In doi_to_url, {0} does not transform to {1}, but to {2}".format(example_doi2,
                         example_url2_int, doi_to_url(example_doi2)))
        self.assertEqual(example_url_int, doi_to_url(example_doi, plos_network=True),
                         "{0} does not transform to {1}".format(example_doi, example_url_int))

    def test_file_conversions(self):
        """
        TODO: What this tests are about!
        """
        self.assertEqual(example_doi, filename_to_doi(example_file),
                         "{0} does not transform to {1}".format(example_file, example_doi))
        self.assertEqual(example_doi2, filename_to_doi(example_file2),
                         "{0} does not transform to {1}".format(example_file2, example_doi2))
        self.assertEqual(example_url, filename_to_url(example_file),
                         "{0} does not transform to {1}".format(example_file, example_url))
        self.assertEqual(example_url2, filename_to_url(example_file2),
                         "{0} does not transform to {1}".format(example_file2, example_url2))
        self.assertEqual(example_url_int, filename_to_url(example_file,
                         plos_network=True),
                         "{0} does not transform to {1}".format(example_file,
                         example_url_int))
        self.assertEqual(example_url2_int, filename_to_url(example_file2,
                         plos_network=True),
                         "{0} does not transform to {1}".format(example_file2,
                         example_url2))


    def test_url_conversions(self):
        """
        TODO: What this tests are about!
        """
        self.assertEqual(example_doi, url_to_doi(example_url),
                         "{0} does not transform to {1}".format(example_url, example_doi))
        self.assertEqual(example_doi2, url_to_doi(example_url2),
                         "{0} does not transform to {1}".format(example_url2, example_doi2))
        self.assertEqual(example_file, url_to_path(example_url, ''),
                         "{0} does not transform to {1}".format(example_url, example_file))
        self.assertEqual(example_file2, url_to_path(example_url2, ''),
                         "{0} does not transform to {1}".format(example_url2, example_file2))
        self.assertEqual(example_doi, url_to_doi(example_url_int),
                         "{0} does not transform to {1}".format(example_url_int, example_doi))
        self.assertEqual(example_doi2, url_to_doi(example_url2_int),
                         "{0} does not transform to {1}".format(example_url2_int, example_doi2))
        self.assertEqual(example_file, url_to_path(example_url_int, ''),
                         "{0} does not transform to {1}".format(example_url_int, example_file))
        # Test temporary commented out.
        # self.assertEqual(example_file2, url_to_path(example_url2_int, plos_network=True),
        #                 "{0} does not transform to {1}".format(example_url2_int, example_file2))


class TestArticleClass(unittest.TestCase):

    def test_class_doi1(self):
        """Tests the methods and properties of the Article class
        Test article DOI: 10.1371/journal.pone.0185809
        XML file is in test directory
        """
        article = Article(class_doi, directory='tests/testdata')
        self.assertEqual(article.check_if_doi_resolves(), "works", 'check_if_doi_resolves does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.check_if_link_works(), True, 'check_if_link_works does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.correct_or_retract_bool(), False, 'correct_or_retract_bool does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_aff_dict(), {'aff001': 'Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands', 'aff002': 'Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany', 'aff003': 'University of Sussex, School of Life Sciences, Falmer, Brighton BN1 9QG, United Kingdom', 'edit1': 'University of Saskatchewan, CANADA'}, 'get_aff_dict does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_body_word_count(), 6646, 'get_body_word_count does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_contributions_dict(), {}, 'get_contributions_dict does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_contributors_info(), [{'contrib_initials': 'CAH', 'given_names': 'Caspar A.', 'surname': 'Hallmann', 'group_name': None, 'ids': [{'id_type': 'orcid', 'id': 'http://orcid.org/0000-0002-4630-0522', 'authenticated': 'true'}], 'rid_dict': {'corresp': ['cor001'], 'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'corresponding', 'editor_type': None, 'email': ['c.hallmann@science.ru.nl'], 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Formal analysis', 'Investigation', 'Methodology', 'Software', 'Validation', 'Visualization', 'Writing – original draft', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'MS', 'given_names': 'Martin', 'surname': 'Sorg', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Data curation', 'Funding acquisition', 'Investigation', 'Methodology', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'EJ', 'given_names': 'Eelke', 'surname': 'Jongejans', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Funding acquisition', 'Investigation', 'Supervision', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'HS', 'given_names': 'Henk', 'surname': 'Siepel', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Investigation', 'Supervision', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'NH', 'given_names': 'Nick', 'surname': 'Hofland', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Formal analysis', 'Resources', 'Software', 'Validation']}, 'footnotes': []}, {'contrib_initials': 'HS', 'given_names': 'Heinz', 'surname': 'Schwan', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Funding acquisition', 'Investigation', 'Methodology', 'Project administration', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'WS', 'given_names': 'Werner', 'surname': 'Stenmans', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Funding acquisition', 'Methodology', 'Project administration', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'AM', 'given_names': 'Andreas', 'surname': 'Müller', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Project administration', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'HS', 'given_names': 'Hubert', 'surname': 'Sumser', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Investigation', 'Methodology', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'TH', 'given_names': 'Thomas', 'surname': 'Hörren', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Investigation', 'Methodology', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'DG', 'given_names': 'Dave', 'surname': 'Goulson', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff003']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['University of Sussex, School of Life Sciences, Falmer, Brighton BN1 9QG, United Kingdom'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Investigation', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'HK', 'given_names': 'Hans', 'surname': 'de Kroon', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Funding acquisition', 'Investigation', 'Methodology', 'Resources', 'Supervision', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'EGL', 'given_names': 'Eric Gordon', 'surname': 'Lamb', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['edit1']}, 'contrib_type': 'editor', 'author_type': None, 'editor_type': None, 'email': None, 'affiliations': ['University of Saskatchewan, CANADA'], 'author_roles': {None: ['Editor']}, 'footnotes': []}], 'get_contributors_info does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_corr_author_emails(), {'cor001': ['c.hallmann@science.ru.nl']}, 'get_corr_author_emails does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_counts(), {'fig-count': '5', 'table-count': '4', 'page-count': '21'}, 'get_counts does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_dates(), {'collection': datetime.datetime(2017, 1, 1, 0, 0), 'epub': datetime.datetime(2017, 10, 18, 0, 0), 'received': datetime.datetime(2017, 7, 28, 0, 0), 'accepted': datetime.datetime(2017, 9, 19, 0, 0)}, 'get_dates does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_fn_dict(), {'coi001': 'The authors have declared that no competing interests exist.', 'cor001': 'c.hallmann@science.ru.nl'}, 'get_fn_dict does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_plos_journal(), "PLOS ONE", 'get_plos_journal does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_related_doi(), None, 'get_related_doi does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.get_url(), "http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0185809&type=manuscript", 'get_url does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.abstract[:100], "Global declines in insects have sparked wide interest among scientists, politicians, and the general", 'abstract does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.authors, [{'contrib_initials': 'CAH', 'given_names': 'Caspar A.', 'surname': 'Hallmann', 'group_name': None, 'ids': [{'id_type': 'orcid', 'id': 'http://orcid.org/0000-0002-4630-0522', 'authenticated': 'true'}], 'rid_dict': {'corresp': ['cor001'], 'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'corresponding', 'editor_type': None, 'email': ['c.hallmann@science.ru.nl'], 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Formal analysis', 'Investigation', 'Methodology', 'Software', 'Validation', 'Visualization', 'Writing – original draft', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'MS', 'given_names': 'Martin', 'surname': 'Sorg', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Data curation', 'Funding acquisition', 'Investigation', 'Methodology', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'EJ', 'given_names': 'Eelke', 'surname': 'Jongejans', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Funding acquisition', 'Investigation', 'Supervision', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'HS', 'given_names': 'Henk', 'surname': 'Siepel', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Investigation', 'Supervision', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'NH', 'given_names': 'Nick', 'surname': 'Hofland', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Formal analysis', 'Resources', 'Software', 'Validation']}, 'footnotes': []}, {'contrib_initials': 'HS', 'given_names': 'Heinz', 'surname': 'Schwan', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Funding acquisition', 'Investigation', 'Methodology', 'Project administration', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'WS', 'given_names': 'Werner', 'surname': 'Stenmans', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Funding acquisition', 'Methodology', 'Project administration', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'AM', 'given_names': 'Andreas', 'surname': 'Müller', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Project administration', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'HS', 'given_names': 'Hubert', 'surname': 'Sumser', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Investigation', 'Methodology', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'TH', 'given_names': 'Thomas', 'surname': 'Hörren', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff002']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Entomological Society Krefeld e.V., Entomological Collections Krefeld, Marktstrasse 159, 47798 Krefeld, Germany'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Data curation', 'Investigation', 'Methodology', 'Resources', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'DG', 'given_names': 'Dave', 'surname': 'Goulson', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff003']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['University of Sussex, School of Life Sciences, Falmer, Brighton BN1 9QG, United Kingdom'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Investigation', 'Writing – review & editing']}, 'footnotes': []}, {'contrib_initials': 'HK', 'given_names': 'Hans', 'surname': 'de Kroon', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'contributing', 'editor_type': None, 'email': None, 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Funding acquisition', 'Investigation', 'Methodology', 'Resources', 'Supervision', 'Writing – review & editing']}, 'footnotes': []}], 'authors does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.corr_author, [{'contrib_initials': 'CAH', 'given_names': 'Caspar A.', 'surname': 'Hallmann', 'group_name': None, 'ids': [{'id_type': 'orcid', 'id': 'http://orcid.org/0000-0002-4630-0522', 'authenticated': 'true'}], 'rid_dict': {'corresp': ['cor001'], 'aff': ['aff001']}, 'contrib_type': 'author', 'author_type': 'corresponding', 'editor_type': None, 'email': ['c.hallmann@science.ru.nl'], 'affiliations': ['Radboud University, Institute for Water and Wetland Research, Animal Ecology and Physiology & Experimental Plant Ecology, PO Box 9100, 6500 GL Nijmegen, The Netherlands'], 'author_roles': {'CASRAI CREDiT taxonomy': ['Conceptualization', 'Formal analysis', 'Investigation', 'Methodology', 'Software', 'Validation', 'Visualization', 'Writing – original draft', 'Writing – review & editing']}, 'footnotes': []}], 'corr_author does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.correct_or_retract, False, 'correct_or_retract does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.counts, {'fig-count': '5', 'table-count': '4', 'page-count': '21'}, 'counts does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.doi, "10.1371/journal.pone.0185809", 'doi does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.dtd, "JATS 1.1d3", 'dtd does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.editor, [{'contrib_initials': 'EGL', 'given_names': 'Eric Gordon', 'surname': 'Lamb', 'group_name': None, 'ids': [], 'rid_dict': {'aff': ['edit1']}, 'contrib_type': 'editor', 'author_type': None, 'editor_type': None, 'email': None, 'affiliations': ['University of Saskatchewan, CANADA'], 'author_roles': {None: ['Editor']}, 'footnotes': []}], 'editor does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.filename, "tests/testdata/journal.pone.0185809.xml", 'filename does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.journal, "PLOS ONE", 'journal does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.local, True, 'local does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.page, "http://journals.plos.org/plosone/article?id=10.1371/journal.pone.0185809", 'page does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.plostype, "Research Article", 'plostype does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.proof, None, 'proof does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.pubdate, datetime.datetime(2017, 10, 18, 0, 0), 'pubdate does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.related_doi, None, 'related_doi does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.title, "More than 75 percent decline over 27 years in total flying insect biomass in protected areas", 'title does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.type_, "research-article", 'type_ does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.url, "http://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0185809&type=manuscript", 'url does not transform correctly for {}'.format(article.doi))
        self.assertEqual(article.word_count, 6646, 'word_count does not transform correctly for {}'.format(article.doi))


if __name__ == "__main__":
    unittest.main()
