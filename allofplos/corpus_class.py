from collections import OrderedDict
import os
import random

from . import corpusdir

from .article_class import Article
from .plos_corpus import get_all_solr_dois
from .transformations import filename_to_doi, doi_to_path



class Corpus():
    """A collection of PLOS articles.
    """

    def __init__(self, directory=corpusdir, plos_network=False):
        """Creation of an article corpus class."""
        self.directory = directory
        self.plos_network = plos_network
        self.reset_memoized_attrs()

    def reset_memoized_attrs(self):
        """Reset attributes to None when instantiating a new corpus object.

        For corpus attributes that are memoized and specific to that particular corpus,
        reset them when creating a new corpus object.
        """
        self._file_doi = None

    @property
    def directory(self):
        """
        :returns: directory of corpus
        :rtype: {str}
        """
        return self._directory

    @directory.setter
    def directory(self, d):
        """
        Reset memoized info when changing the path to the corpus.
        """
        self.reset_memoized_attrs()
        self._directory = d

    @property
    def file_doi(self):
        """An ordered dict that maps every corpus file to its accompanying DOI.
        Used to generate both DOI and file lists for the corpus; both also ordered.
        """
        if self._file_doi is None:
            self._file_doi = OrderedDict((file_, filename_to_doi(file_)) for file_ in os.listdir(self.directory)
                                         if file_.endswith('.xml') and 'DS_Store' not in file_)
        else:
            pass
        return self._file_doi

    @property
    def files(self):
        """List of article XML files in the corpus directory."""

        if self._files is None:
            if os.path.isdir(self.directory):
                file_list = [file_ for file_ in os.listdir(self.directory) if file_.endswith('.xml') and
                             'DS_Store' not in file_]
            else:
                # if directory doesn't exist, return empty list
                file_list = []
            self._files = file_list
        else:
            pass

        return self._files

    @property
    def dois(self):
        """List of DOIs of the articles in the corpus directory."""

        if self._dois is None:
            doi_list = [filename_to_doi(article) for article in self.files]
            self._dois = doi_list
        else:
            pass

        return self._dois


    def random_dois(self, count):
        """
        Gets a list of random DOIs. Construct from local files in
        corpusdir, otherwise tries Solr DOI list as backup.
        :param directory: directory of articles for class object
        :param count: specify how many DOIs are to be returned
        :return: a list of random DOIs for analysis
        """
        try:
            doi_list = self.dois
            sample_doi_list = random.sample(doi_list, count)
        except OSError:
            doi_list = get_all_solr_dois()
            sample_doi_list = random.sample(doi_list, count)

        return sample_doi_list


    # @symlinks.setter
    # def symlinks(self, value):
    #     """Sets a corpus object using a set of dois.

    #     Converts a filename to DOI using an existing function.
    #     :param value: filename
    #     :type value: string
    #     """
    #     self.doi = filename_to_doi(value)

    @classmethod
    def from_dois(cls, dois, source=corpusdir, destination='testdir'):
        """Initiate a corpus object using a doi list with a source directory.
        All DOIs must correspond to articles in the source directory
        """
        try:
            os.mkdir(destination)
        except FileExistsError:
            print(os.listdir(destination))
            return None
        for doi in dois:
            os.symlink(doi_to_path(doi, directory=source),
                       doi_to_path(doi, directory=destination))
        return cls(directory=destination)
