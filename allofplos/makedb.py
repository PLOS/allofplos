#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Make a SQLite DB out of articles XML files
"""

import argparse
import datetime
import os
from itertools import islice

from tqdm import tqdm
import sqlite3

from peewee import Model, CharField, ForeignKeyField, TextField, \
    DateTimeField, BooleanField, IntegerField, IntegrityError
from playhouse.sqlite_ext import SqliteExtDatabase

from allofplos.corpus import Corpus
from allofplos.transformations import filename_to_doi, convert_country
from allofplos import starterdir
from allofplos.article import Article

journal_title_dict = {
    'PLOS ONE': 'PLOS ONE',
    'PLOS GENETICS': 'PLOS Genetics',
    'PLOS GENET': 'PLOS Genetics',
    'PLOS NEGLECTED TROPICAL DISEASES': 'PLOS Neglected Tropical Diseases',
    'PLOS NEGL TROP DIS': 'PLOS Neglected Tropical Diseases',
    'PLOS BIOLOGY': 'PLOS Biology',
    'PLOS BIOL': 'PLOS Biology',
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


parser = argparse.ArgumentParser()
parser.add_argument('--db', action='store', help=
                    'Name the db', default='ploscorpus.db')
parser.add_argument('--random', action='store', type=int, help=
                    'Number of articles in a random subset. '
                    'By default will use all articles')
parser.add_argument('--starterdb', action='store_true', help=
                    'Make the starter database', dest='starter')
args = parser.parse_args()

# TODO: Put a warning that the DB will be deleted
if os.path.isfile(args.db):
    os.remove(args.db)

if args.starter:
    if os.path.isfile('starter.db'):
        os.remove('starter.db')
    db = SqliteExtDatabase('starter.db')
else:
    db = SqliteExtDatabase(args.db)

class BaseModel(Model):
    class Meta:
        database = db

class Journal(BaseModel):
    """
    Journal table stores journals values. It is used in the PLOSArticle table.
    Fields:
    journal: Journal name. Based on the values of journal_title_dict
    """
    journal = CharField(unique=True)

class ArticleType(BaseModel):
    """
    ArticleType table stores article types used in PLOSArticle table.
    Fields:
    article_type: Article type such as Research Article, Retraction,
      Essay, Perspective and others.
    """
    article_type = CharField(unique=True)

class Country(BaseModel):
    """
    Country table stores countries that are related with the corresponding
      author.
    Fields:
    country: Country.
    """
    country = CharField(unique=True)

class Affiliations(BaseModel):
    """
    Affiliations table stores affiliations that are related with the
      corresponding author.
    Fields:
    affiliations: Author affiliations such as "Department of Public Health,
      University of Helsinki, Finland".
    """
    affiliations = CharField(unique=True)

class Subjects(BaseModel):
    """
    Subjects table stores subjects that are related to PLOSArticle table by
      using a link table (since an article may have multiple subjects)
    Fields:
    subjects: Subjects like "Molecular Biology", "Cell processes" and so on.
    """
    subjects = CharField(unique=True)

class CorrespondingAuthor(BaseModel):
    """
    CorrespondingAuthor table stores the information of the corresponding
      author.
    Fields:
    corr_author_email: e-mail of the corresponding author
    tld: Top Level Domain, last part of the email, such as .ar, .es, .com.
    given_name: Given name of the author.
    surname: Surname of the author.
    group_name: Name of the group if a group is the author. If not, it is null.
    affiliation: Author affiliation, this is a linked field.
    country: Country of the author, this is a linked field.
    """
    corr_author_email = CharField(unique=True)
    tld = TextField(null=True)
    given_name = TextField(null=True)
    surname = TextField(null=True)
    group_name = TextField(null=True)
    affiliation = ForeignKeyField(Affiliations, related_name='aff')
    country = ForeignKeyField(Country, related_name='aff')

class JATSType(BaseModel):
    """
    JATSType table stores the article type using the JATS (Journal Article
      Tag Suite) standard (https://jats.nlm.nih.gov/).
    Fields:
    jats_type: JATS type, such as "research-article", "discussion", "editorial".
    """
    jats_type = CharField(unique=True)

class PLOSArticle(BaseModel):
    """
    PLOSArticle table is the main table of the database. It stores the articles.
    Fields:
    DOI: DOI for the article. For example: 10.1371/journal.pcbi.0030199
    abstract: Abstract for the article.
    title: Title for the article.
    plostype = Article type (internal PLOS classification), this is a linked
      field.
    journal = Journal name, this is a linked field.
    created_date = Article creation date. For example: 2006-04-11 00:00:00
    word_count = Amount of words in the article.
    JATS_type = Article type (JATS classification), this is a linked field.
    """
    DOI = TextField(unique=True)
    abstract = TextField()
    title = TextField()
    plostype = ForeignKeyField(ArticleType, related_name='arttype')
    journal = ForeignKeyField(Journal, related_name='journals')
    created_date = DateTimeField(default=datetime.datetime.now)
    word_count = IntegerField()
    JATS_type = ForeignKeyField(JATSType, related_name='jats')

class SubjectsPLOSArticle(BaseModel):
    """
    SubjectsPLOSArticle is a link table to relate subject with articles
    Fields:
    subject: This field is linked to Subjects table.
    article: This field is linked to PLOSArticle table.
    """
    subject = ForeignKeyField(Subjects)
    article = ForeignKeyField(PLOSArticle)

class CoAuthorPLOSArticle(BaseModel):
    """
    CoAuthorPLOSArticle is a link table to relate a co-author with a PLOS
      article.
    Fields:
    corr_author: This field is linked to CorrespondingAuthor table.
    article: This field is linked to PLOSArticle table.
    """
    corr_author = ForeignKeyField(CorrespondingAuthor)
    article = ForeignKeyField(PLOSArticle)

db.connect()
db.create_tables([Journal, PLOSArticle, ArticleType, CoAuthorPLOSArticle,
                  CorrespondingAuthor, JATSType, Affiliations, Country,
                  SubjectsPLOSArticle, Subjects])


corpus_dir = starterdir if args.starter else None
all_files = Corpus(corpus_dir)
num_files = len(all_files) if args.random is None else args.random

for article in tqdm(islice(all_files, args.random), total=num_files):
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
        DOI=article.doi,
        journal = journal,
        abstract=article.abstract.replace('\n', '').replace('\t', ''),
        title = article.title.replace('\n', '').replace('\t', ''),
        plostype = article_type,
        created_date = article.pubdate,
        word_count=article.word_count,
        JATS_type = j_type)
    # Get subject information
    taxonomy_set = set()
    taxonomy = article.taxonomy
    for values in taxonomy.values():
        for value in values:
            for taxon in value:
                taxonomy_set.add(taxon)
    for taxon in taxonomy_set:
        with db.atomic() as atomic:
            try:
                subject = Subjects.create(subjects = taxon)
            except (sqlite3.IntegrityError, IntegrityError):
                db.rollback()
                subject = Subjects.get(Subjects.subjects == taxon)
        SubjectsPLOSArticle.create(
                subject = subject,
                article = p_art
            )
    if article.authors:
        iterable_authors = article.authors
    else:
        iterable_authors = []
    for auths in iterable_authors:
        if auths['email']:
            with db.atomic() as atomic:
                if auths['affiliations']:
                    author_aff = auths['affiliations'][0]
                else:
                    author_aff = 'N/A'
                try:
                    aff = Affiliations.create(affiliations = author_aff)
                except (sqlite3.IntegrityError, IntegrityError):
                    db.rollback()
                    aff = Affiliations.get(Affiliations.affiliations ==
                                           author_aff)
            with db.atomic() as atomic:
                try:
                    if auths['affiliations'][0] == '':
                        country_from_aff = 'N/A'
                    else:
                        country_from_aff = auths['affiliations'][0].\
                                           split(',')[-1].strip()
                except IndexError:
                    country_from_aff = 'N/A'
                country_from_aff = convert_country(country_from_aff)
                try:
                    country = Country.create(country = country_from_aff)
                except IntegrityError:
                    db.rollback()
                    country = Country.get(Country.country == country_from_aff)

            try:
                co_author = CorrespondingAuthor.create(
                    corr_author_email = auths['email'][0],
                    tld = auths['email'][0].split('.')[-1],
                    given_name = auths['given_names'],
                    surname = auths['surname'],
                    group_name = auths['group_name'],
                    affiliation = aff,
                    country = country
                    )
            except IntegrityError:
                co_author = CorrespondingAuthor.\
                            get(CorrespondingAuthor.corr_author_email == auths['email'][0])
            coauthplosart = CoAuthorPLOSArticle.create(
                    corr_author = co_author,
                    article = p_art
                )
