from collections import OrderedDict
from pathlib import Path
import os
import random

from . import corpusdir

from .article_class import Article
from .gdrive import (get_zip_metadata, download_file_from_google_drive, unzip_articles,
                    zip_id, local_zip)
from .transformations import filename_to_doi, doi_to_path


class Corpus():
    """A collection of PLOS articles.
    """

    def __init__(self, directory=corpusdir, plos_network=False, extension='.xml'):
        """Creation of an article corpus class."""
        self.directory = directory
        self.plos_network = plos_network
        self.extension = extension
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

    def __repr__(self):
        """Value of a corpus object when you call it directly on the command line.

        Shows the directory location of the corpus
        :returns: directory
        :rtype: {str}
        """
        out = "Corpus location: {0}\nNumber of files: {1}".format(self.directory, len(self.files))
        return out

    @property
    def file_doi(self):
        """An ordered dict that maps every corpus file to its accompanying DOI.
        Used to generate both DOI and file lists for the corpus; both also ordered.
        """
        if self._file_doi is None:
            self._file_doi = OrderedDict((file_, filename_to_doi(file_)) for file_ in os.listdir(self.directory)
                                         if file_.endswith(self.extension) and 'DS_Store' not in file_)
        else:
            pass
        return self._file_doi

    @property
    def files(self):
        """List of article XML files in the corpus directory."""

        return list(self.file_doi.keys())

    @property
    def dois(self):
        """List of DOIs of the articles in the corpus directory."""

        return list(self.file_doi.values())

    def random_dois(self, count):
        """
        Gets a list of random DOIs. Construct from local files in
        corpusdir. Length of list specified in `count` parameter.
        :param directory: directory of articles for class object
        :param count: specify how many DOIs are to be returned
        :return: a list of random DOIs for analysis
        """
        doi_list = self.dois
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
    def create(cls, directory=corpusdir, overwrite=False):
        """ Create a PLOS corpus from scratch.

        Downloads and unzips the main PLOS .zip file hosted on Google Drive.
        :param directory: directory to download and unzip zip file
        :param overwrite: whether to overwrite existing files, defaults to False
        """
        os.makedirs(directory, exist_ok=True)
        if overwrite is False and len(os.listdir(directory)) > 2:
            print("Can't create corpus at {}; files already exist.".format(directory))
            return None
        else:
            zip_date, zip_size, metadata_path = get_zip_metadata()
            zip_path = download_file_from_google_drive(zip_id, local_zip, file_size=zip_size,
                                                       destination=directory)
            unzip_articles(file_path=zip_path, extract_directory=directory)
            os.remove(metadata_path)
            print("Corpus created with {} files".format(len(os.listdir(directory))))
            return cls(directory=directory)


    @classmethod
    def from_dois(cls, dois, source=corpusdir, destination='testdir', overwrite=True):
        """Initiate a corpus object using a doi list, with a source directory.
        Uses symlinks instead of creating duplicate article objects.
        All DOIs must correspond to articles in the source directory.
        Will not work if files already exist in testdir. Will erase existing symlinks
        by default.
        :param dois: list of PLOS DOIs
        :param source: directory with PLOS article XML files
        :param destination: new directory where will create symlinks to articles
        :param overwrite: if symlinks already exist in testdir, overwrite them
        """
        os.makedirs(destination, exist_ok=True)

        # make sure that all files exist in the source
        corpus_source = Corpus(directory=source)
        source_dois = corpus_source.dois
        if set(dois).issubset(set(source_dois)):
            pass
        else:
            print("unable to create links; not all DOIs represented in source directory.")
            return None

        # if already files/symlinks at destination
        if os.listdir(destination) and overwrite is True:
            print("removing existing symlinks...")
            p = Path(destination)
            for item in p.iterdir():
                if Path(item).is_symlink():
                    Path(item).unlink()
                elif Path(item).is_file():
                    if '.DS_Store' not in item.name:
                        print("files already exist in destination; aborting corpus creation")
                        return None
                    else:
                        pass
        elif os.listdir(destination) and overwrite is False:
            print("ignoring existing files in destination directory")
        else:
            pass

        # create the symlinks
        if dois:
            for doi in dois:
                os.symlink(doi_to_path(doi, directory=source),
                           doi_to_path(doi, directory=destination))
            print("New corpus created with {} files".format(len(dois)))
            return cls(directory=destination)
        else:
            print("No DOIs in DOI list; corpus not created")
            return None
