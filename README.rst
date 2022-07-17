.. image:: https://api.travis-ci.org/PLOS/allofplos.svg?branch=master
   :target: https://travis-ci.org/PLOS/allofplos
   :alt: Build Status

All of Plos (allofplos)
=======================

Copyright (c) 2017, Public Library of Science. MIT License, see
LICENSE.txt for more information.

Why allofplos?
--------------

This is for downloading/updating/maintaining a repository of all PLOS
XML article files. This can be used to have a copy of the PLOS text
corpus for further analysis. Use this program to download all PLOS XML
article files instead of doing web scraping.

**NOTE**: This software is not stable, we consider it beta state and will
be in this stage until version 1.0. This means that programming interface
may change and after a new version a full corpus download may be required.

Installation instructions
-------------------------

This program requires Python 3.8+.

Using pip:

``$ pip install allofplos``

This should install *allofplos* and requirements. At this stage you are ready to go.

If you want to manually install from source (for example for development purposes), first clone the project repository:

``$ git clone git@github.com:PLOS/allofplos.git``

Install Python dependencies inside the newly created virtual environment:

``$ pipenv install``

How to run the program
----------------------

Execute the following command.

``$ python -m allofplos.update``

or, if running from source:

``$ pipenv run python -m allofplos.update``

The first time it runs it will download a >4.4 Gb zip file
(**allofplos_xml.zip**) with all the XML files inside.
**Note**: Make sure that you have enough space in your device for the
zip file and for its content before running this command (at least 30Gb).
After this file is downloaded, it will extract its contents into the
allofplos\_xml directory inside your installation of *allofplos*.

If you want to see the directory on your file system where this is installed run

``python -c "from allofplos import get_corpus_dir; print(get_corpus_dir())"``

If you ever downloaded the corpus before, it will make an incremental
update to the existing corpus. The script:

-  checks for and then downloads to a temporary folder individual new articles that have been published
-  of those new articles, checks whether they are corrections (and
   whether the linked corrected article has been updated)
-  checks whether there are VORs (Versions of Record) for uncorrected
   proofs in the main articles directory and downloads those
-  checks whether the newly downloaded articles are uncorrected proofs
   or not after all of these checks, it moves the new articles into the
   main articles folder.

Here’s what the print statements might look like on a typical run:

::

    147 new articles to download.
    147 new articles downloaded.
    3 amended articles found.
    0 amended articles downloaded with new xml.
    Creating new text list of uncorrected proofs from scratch.
    No new VOR articles indexed in Solr.
    17 VOR articles directly downloaded.
    17 uncorrected proofs updated to version of record. 44 uncorrected proofs remaining in uncorrected proof list.
    9 uncorrected proofs found. 53 total in list.
    Corpus started with 219792 articles.
    Moving new and updated files...
    164 files moved. Corpus now has 219939 articles.

How to run the tests
--------------------

To run the tests, you will need to install *allofplos* with its testing
dependencies. These testing dependencies include ``pytest``, which we will use
to run the tests.

``$ pipenv run python -m pytest``

It should return something like this:

.. code::

  collected 20 items

  allofplos/tests/test_corpus.py ............                       [ 60%]
  allofplos/tests/test_unittests.py ........                        [100%]

  ==================== 20 passed in 0.36 seconds =========================


Community guidelines
--------------------

If you wish to contribute to this project please open a ticket in the
GitHub repo at https://github.com/PLOS/allofplos/issues. For support
requests write to mining@plos.org

Citing This Library
-------------------

*allofplos* is published in the proceedings of the SciPy 2018.
DOI `10.25080/Majora-4af1f417-009 <https://doi.org/10.25080/Majora-4af1f417-009>`_ refers to all versions of allofplos.

If you want to cite allofplos using Bibtex:

::

   @InProceedings{ elizabeth_seiver-proc-scipy-2018,
     author    = { Elizabeth Seiver and M Pacer and Sebastian Bassi },
     title     = { Text and data mining scientific articles with allofplos },
     booktitle = { Proceedings of the 17th Python in Science Conference },
     pages     = { 61 - 64 },
     year      = { 2018 },
     editor    = { Fatih Akici and David Lippa and Dillon Niederhut and M Pacer },
     doi       = { 10.25080/Majora-4af1f417-009 }
   }
