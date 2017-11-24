#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Make a SQLite DB out of articles XML files
"""

from bs4 import BeautifulSoup
import os
import random
import progressbar

from transformations import filename_to_doi
from article_class import Article

from peewee import Model, CharField, ForeignKeyField, TextField, \
    DateTimeField, BooleanField, IntegerField, IntegrityError
from playhouse.sqlite_ext import SqliteExtDatabase
import datetime

corpusdir = 'allofplos_xml'

journal_title_dict = {
'PLOS ONE':'PLOS ONE',
'PLOS GENETICS':' PLOS Genetics',
'PLOS GENET': 'PLOS Genetics',
'PLOS NEGLECTED TROPICAL DISEASES':'PLOS Neglected Tropical Diseases',
'PLOS NEGL TROP DIS':'PLOS Neglected Tropical Diseases',
'PLOS BIOLOGY':'PLOS Biology',
'PLOS BIOL':'PLOS Biology',
'PLOS CLINICAL TRIALS': 'PLOS Clinical Trials',
'PLOS MEDICINE':'PLOS Medicine',
'PLOS MEDICIN': 'PLOS Medicine',
'PLOS MED': 'PLOS Medicine',
'PLOS PATHOG': 'PLOS Pathogens',
'PLOS PATHOGENS': 'PLOS Pathogens',
'PLOS COMPUTATIONAL BIOLOGY': 'PLOS Computational Biology',
'PLOS COMPUT BIOL': 'PLOS Computational Biology',
'PLOS CLINICAL TRIALS': 'PLOS Clinical Trials',
}

db = SqliteExtDatabase('my_database.db')

class BaseModel(Model):
    class Meta:
        database = db

class Journal(BaseModel):
    journal = CharField(unique=True)

class ArticleType(BaseModel):
    article_type = CharField(unique=True)

class CorrespondingAuthor(BaseModel):
    corr_author_email = CharField(unique=True)
    tld = TextField(null=True)
    given_name = TextField(null=True)
    surname = TextField(null=True)
    group_name = TextField(null=True)

class JATSType(BaseModel):
    jats_type = CharField(unique=True)

class PLOSArticle(BaseModel):
    DOI = TextField(unique=True)
    abstract = TextField()
    title = TextField()
    plostype = ForeignKeyField(ArticleType, related_name='arttype')
    journal = ForeignKeyField(Journal, related_name='journals')
    created_date = DateTimeField(default=datetime.datetime.now)
    word_count = IntegerField()
    JATS_type = ForeignKeyField(JATSType, related_name='jats')

class CoAuthorPLOSArticle(BaseModel):
    corr_author = ForeignKeyField(CorrespondingAuthor)
    article = ForeignKeyField(PLOSArticle)

db.connect()
try:
    db.create_tables([Journal, PLOSArticle, ArticleType,
                      CoAuthorPLOSArticle, CorrespondingAuthor,
                      JATSType])
except:
    pass

allfiles = os.listdir(corpusdir)
randomfiles = random.sample(allfiles, 50)
#max_value = len(randomfiles)
max_value = len(allfiles)
bar = progressbar.ProgressBar(redirect_stdout=True, max_value=max_value)
for i, file_ in enumerate(allfiles):
#for i, file_ in enumerate(randomfiles):
    #print(file_)
    doi = filename_to_doi(file_)
    article = Article(doi)
    journal_name = journal_title_dict[article.journal.upper()]
    with db.atomic() as atomic:
        try:
            journal = Journal.create(journal = journal_name)
        except IntegrityError:
            db.rollback()
            journal = Journal.get(Journal.journal == journal_name)
    with db.atomic() as atomic:
        try:
            article_type = ArticleType.create(article_type = article.plostype)
        except IntegrityError:
            db.rollback()
            article_type = ArticleType.get(ArticleType.article_type == article.plostype)
    with db.atomic() as atomic:
        try:
            j_type = JATSType.create(jats_type = article.type_)
        except IntegrityError:
            db.rollback()
            j_type = JATSType.get(JATSType.jats_type == article.type_)
    p_art = PLOSArticle.create(
        DOI = doi,
        journal = journal,
        abstract=article.abstract.replace('\n', '').replace('\t', ''),
        title = article.title.replace('\n', '').replace('\t', ''),
        plostype = article_type,
        created_date = article.pubdate,
        word_count=article.word_count,
        JATS_type = j_type)
    ##p_art.save()
    for auths in article.authors:
        if auths['email']:
            try:
                co_author = CorrespondingAuthor.create(
                    corr_author_email = auths['email'][0],
                    tld = auths['email'][0].split('.')[-1],
                    given_name = auths['given_names'],
                    surname = auths['surname'],
                    group_name = auths['group_name']
                    )
                co_author.save()
            except IntegrityError:
                co_author = CorrespondingAuthor.\
                            get(CorrespondingAuthor.corr_author_email == auths['email'][0])
            coauthplosart = CoAuthorPLOSArticle.create(
                    corr_author = co_author,
                    article = p_art
                )
            ##coauthplosart.save()
    bar.update(i+1)
bar.finish()
