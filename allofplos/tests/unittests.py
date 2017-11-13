import os
import unittest

from allofplos.plos_corpus import INT_URL_TMP, EXT_URL_TMP
from allofplos.transformations import (doi_to_path, url_to_path, filename_to_doi, url_to_doi,
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


class TestDOIMethods(unittest.TestCase):

    def test_doi_conversions(self):
        """
        TODO: What this tests are about!
        """
        self.assertEqual(os.path.join(corpusdir,example_file), doi_to_path(example_doi), "{0} does not transform to {1}".format(example_doi, example_file))
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
        #self.assertEqual(example_file2, url_to_path(example_url2_int, plos_network=True),
        #                 "{0} does not transform to {1}".format(example_url2_int, example_file2))



if __name__ == "__main__":
    unittest.main()
