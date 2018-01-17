#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Make seed data. This script is for the creation of the seed data directory out
of the data in the plos_corpus directory. Should be used only for initial seed
data generation. It is a mantainance script not intented to be used as a
regular tool.
"""

import os
from shutil import copyfile

from . import get_corpus_dir
from .transformations import doi_to_path

seed_directory = 'seed_corpus'

try:
    os.mkdir(seed_directory)
except FileExistsError:
    pass

seed_dois = []
for doi in open('dois.txt'):
    seed_dois.append(doi.replace('\n',''))

for doi in seed_dois:
    # Copy file from get_corpus_dir()
    article_path = doi_to_path(doi, get_corpus_dir())
    file_name = os.path.basename(article_path)
    copyfile(article_path, os.path.join(seed_directory,file_name))
