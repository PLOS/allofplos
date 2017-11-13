#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Make a SQLite DB out of articles XML files
"""

from bs4 import BeautifulSoup
import os
import progressbar

corpusdir = 'allofplos_xml'

journal_set = set()
subject_set = set()

allfiles = os.listdir(corpusdir)
max_value = len(allfiles)
bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
for i, file_ in enumerate(allfiles):
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
    journal_set.add(journal)
    subject = soup.find('article-categories').find('subj-group').subject.text
    subject_set.add(subject)
    bar.update(i+1)
    #print(journal)
    #print(subject)
    #print('============================')

bar.finish()
print(journal)
print(subject)

'''
if soup.find('article-categories').find('subj-group').has_attr('subj-group-type'):
    d = soup.find('article-categories').find('subj-group').attrs
    if d['subj-group-type'] == 'heading':
        subject = soup.find('article-categories').find('subj-group').subject.text
'''
