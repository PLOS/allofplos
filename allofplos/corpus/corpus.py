import os

from random import Random
from collections import OrderedDict
from itertools import islice

from .. import get_corpus_dir, Article
from ..transformations import filename_to_doi, doi_to_path


class Corpus:
    """A collection of PLOS articles."""

    def __init__(self, directory=None, extension='.xml', seed=None):
        """Creation of an article corpus class."""
        if directory is None:
            directory = get_corpus_dir()
        self.directory = directory
        self.extension = extension
        self.random = Random(seed)

    def __repr__(self):
        """Value of a corpus object when you call it directly on the command line.

        Shows the directory location of the corpus
        :returns: directory
        :rtype: {str}
        """
        out = "Corpus location: {0}\nNumber of files: {1}".format(self.directory, len(self.files))
        return out
    
    def __len__(self):
        return len(self.dois)
    
    def __iter__(self):
        return (article for article in self.random_article_generator)
    
    def __getitem__(self, key):
        
        if isinstance(key, int):
            return Article(self.dois[key], directory=self.directory)
        elif isinstance(key, slice):
            return (Article(doi, directory=self.directory) 
                    for doi in self.dois[key])
        elif key not in self.dois:
            path= doi_to_path(key, directory=self.directory)
            raise IndexError(("You attempted get {doi} from "
                              "the corpus at \n{directory}. \n"
                              "This would point to: {path}. \n"
                              "Is that the file that was intended?"
                              ).format(doi=key, 
                                       directory=self.directory,
                                       path=path
                                      )
                            )
        else:
            return Article(key, directory=self.directory)

    def __contains__(self, value):
        is_in = False
        if isinstance(value, Article):
            is_in = value.doi in self.dois and value.directory == self.directory
        elif isinstance(value, str):
            doi_in = value in self.dois
            file_in = value in self.files
            filepath_in = value in self.filepaths
            is_in = doi_in or file_in or filepath_in
        return is_in
        
    @property
    def iter_file_doi(self):
        """Generator that returns filename, doi tuples for every file in the corpus.

        Used to generate both DOI and file generators for the corpus.
        """
        return ((file_, filename_to_doi(file_))
                for file_ in sorted(os.listdir(self.directory))
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
        return list(self.iter_filepaths)

    @property
    def article_generator(self):
        """iterator of articles"""
        return (Article(doi, directory=self.directory) 
                for doi in self.iter_dois)

    @property
    def random_article_generator(self):
        """iterator over random articles"""
        return (Article(doi, directory=self.directory) 
                for doi in self.iter_random_dois)

    @property
    def random_article(self):
        return next(self.random_article_generator)

    def random_sample(self, count):
        """
        Creates a generator for random articles. 

        Length of generator specified in `count` parameter.

        :param count: specify how many articles are to be returned
        :return: a generator of random articles for analysis
        """

        return islice(self.random_article_generator, count)

    @property
    def iter_random_dois(self):
        return (doi for doi in self.random.sample(self.dois, len(self)))

    @property
    def random_doi(self):
        return next(self.iter_random_dois)

    def random_dois(self, count):
        """
        Gets a list of random DOIs found in the corpus.

        Length of list specified in `count` parameter.
        :param count: specify how many DOIs are to be returned
        :return: a list of random DOIs for analysis
        """

        return list(islice(self.iter_random_dois, count))
