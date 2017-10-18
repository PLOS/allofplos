import lxml.etree as et
import operator
import os

from plos_corpus import filename_to_doi
from plos_regex import validate_doi

# Main directory of article XML files
corpusdir = 'allofplos_xml'

# Temp folder for downloading and processing new articles
newarticledir = 'new_plos_articles'

# URL bases for PLOS's raw article XML
EXT_URL_TMP = 'http://journals.plos.org/plosone/article/file?id={0}&type=manuscript'
INT_URL_TMP = 'http://contentrepo.plos.org:8002/v1/objects/mogilefs-prod-repo?key={0}.XML'
URL_TMP = EXT_URL_TMP


class Article:
    plos_prefix = ''

    def __init__(self, doi, directory=None):
        self.doi = doi
        if directory is None:
            self.directory = corpusdir
        else:
            self.directory = directory
        self._tree = None
        self._local = None

    doi = property(operator.attrgetter('_doi'))

    @doi.setter
    def doi(self, d):
        if validate_doi(d) is False:
            raise Exception("Invalid format for PLOS DOI")
        self._doi = d

    def get_path(self):
        article_path = os.path.join(self.directory, self.doi.lstrip('10.1371/') + '.xml')
        return article_path

    def get_local_bool(self):
        article_path = self.get_path()
        return os.path.isfile(article_path)

    def get_local_element_tree(self, article_path=None):
        if article_path is None:
            article_path = self.get_path()
        if self.local:
            local_element_tree = et.parse(article_path)
            return local_element_tree
        else:
            print("Local article file not found: {}".format(article_path))

    def get_local_xml(self, article_tree=None):
        if article_tree is None:
            article_tree = self.get_local_element_tree()
        local_xml = et.tostring(article_tree, method='xml', encoding='unicode')
        return local_xml

    @property
    def xml(self):
        return self.get_local_xml()

    def get_url(self, plos_network=False):
        URL_TMP = INT_URL_TMP if plos_network else EXT_URL_TMP
        return URL_TMP.format(self.doi)

    def get_remote_element_tree(self, url=None):
        if url is None:
            url = self.get_url()
        remote_element_tree = et.parse(url)
        return remote_element_tree

    def get_remote_xml(self, article_tree=None):
        if article_tree is None:
            article_tree = self.get_remote_element_tree()
        remote_xml = et.tostring(article_tree, method='xml', encoding='unicode')
        return remote_xml

    @property
    def xml(self):
        return self.get_local_xml()

    @property
    def tree(self):
        if self._tree is None:
            return self.get_local_element_tree()
        else:
            return self._tree

    @property
    def url(self):
        return self.get_url(plos_network=self.plos_network)

    @property
    def filename(self):
        return self.get_path()

    @property
    def local(self):
        if self._local is None:
            return self.get_local_bool()
        else:
            return self._local

    @filename.setter
    def filename(self, value):
        self.doi = filename_to_doi(value)

    @classmethod
    def from_filename(cls, filename):
        return cls(filename_to_doi(filename))
