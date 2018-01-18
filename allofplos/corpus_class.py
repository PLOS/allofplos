from collections import OrderedDict
import os
import random

from . import get_corpus_dir, Article
from .transformations import filename_to_doi, doi_to_path


class Corpus():
    """A collection of PLOS articles."""

    def __init__(self, directory=None, plos_network=False, extension='.xml'):
        """Creation of an article corpus class."""
        if directory is None:
            directory = get_corpus_dir()
        self.directory = directory
        self.plos_network = plos_network
        self.extension = extension

    def __repr__(self):
        """Value of a corpus object when you call it directly on the command line.

        Shows the directory location of the corpus
        :returns: directory
        :rtype: {str}
        """
        out = "Corpus location: {0}\nNumber of files: {1}".format(self.directory, len(self.files))
        return out

    @property
    def iter_file_doi(self):
        """Generator that returns filename, doi tuples for every file in the corpus.

        Used to generate both DOI and file generators for the corpus. 
        """
        return ((file_, filename_to_doi(file_))
                for file_ in os.listdir(self.directory)
                if file_.endswith(self.extension) and 'DS_Store' not in file_)

    @property
    def file_doi(self):
        """An ordered dict that maps every corpus file to its accompanying DOI."""
        return OrderedDict(self.iter_file_doi)

    @property
    def iter_files(self):
        """Generator of article XML filenames in the corpus directory."""

        return (x[0] for x in self.iter_file_doi)

    @property
    def iter_dois(self):
        """Generator of DOIs of the articles in the corpus directory.

        Use for looping through all corpus articles with the Article class.
        """

        return (x[1] for x in self.iter_file_doi)

    @property
    def iter_filepaths(self):
        """Generator of article XML files in corpus directory, including the full path."""
        return (os.path.join(self.directory, fname) for fname in self.iter_files)

    @property
    def files(self):
        """List of article XML files in the corpus directory."""

        return list(self.iter_files)

    @property
    def dois(self):
        """List of DOIs of the articles in the corpus directory."""

        return list(self.iter_dois)

    @property
    def filepaths(self):
        """List of article XML files in corpus directory, including the full path."""
        return [os.path.join(self.directory, fname) for fname in self.iter_files]

    def random_dois(self, count):
        """
        Gets a list of random DOIs. Construct from local files in
        corpus directory. Length of list specified in `count` parameter.
        :param count: specify how many DOIs are to be returned
        :return: a list of random DOIs for analysis
        """
        doi_list = self.dois
        sample_doi_list = random.sample(doi_list, count)

        return sample_doi_list
