#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Make a SQLite DB out of articles XML files
"""

from bs4 import BeautifulSoup
import os

corpusdir = 'allofplos_xml2'


for file_ in os.listdir(corpusdir):
    #print(os.path.join(corpusdir, file_))
    #print(file_)
    sample = open(os.path.join(corpusdir, file_)).read()
    soup = BeautifulSoup(sample, 'lxml')
    #import pdb; pdb.set_trace()
    try:
        journal = soup.find('journal-title').get_text(strip=True)
    except AttributeError:
        for jid in soup.findAll('journal-id'):
            if jid['journal-id-type'] == 'nlm-ta':
                journal = jid.text
                break
    subject = soup.find('article-categories').find('subj-group').subject.text
    #print(journal)
    #print(subject)
    #print('============================')


'''
if soup.find('article-categories').find('subj-group').has_attr('subj-group-type'):
    d = soup.find('article-categories').find('subj-group').attrs
    if d['subj-group-type'] == 'heading':
        subject = soup.find('article-categories').find('subj-group').subject.text
'''
