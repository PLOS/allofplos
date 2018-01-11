#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Make starter data. This script is for the creation of the starter data directory out
of the data in the plos_corpus directory. Should be used only for initial starter
data generation. It is a mantainance script not intented to be used as a
regular tool.
"""

import os
from shutil import copyfile

from . import get_corpus_dir
from .transformations import doi_to_path

starter_directory = 'starter_corpus'

try:
    os.mkdir(starter_directory)
except FileExistsError:
    pass

starter_dois = []
for doi in open('dois.txt'):
    starter_dois.append(doi.replace('\n',''))

for doi in starter_dois:
    # Copy file from get_corpus_dir()
    article_path = doi_to_path(doi, get_corpus_dir())
    file_name = os.path.basename(article_path)
    copyfile(article_path, os.path.join(starter_directory,file_name))
