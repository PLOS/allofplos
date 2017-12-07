""" This is an example on how to convert the SQLite DB into a class model to
    make queries without using SQL syntax. This example uses peewee as ORM.
    It should be used as a template, the end user could edit it to fit their
    needs.
    TODO: Add more sample queries.
"""

from peewee import *

database = SqliteDatabase('ploscorpus.db', **{})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class Affiliations(BaseModel):
    affiliations = CharField(unique=True)

    class Meta:
        db_table = 'affiliations'

class Articletype(BaseModel):
    article_type = CharField(unique=True)

    class Meta:
        db_table = 'articletype'

class Jatstype(BaseModel):
    jats_type = CharField(unique=True)

    class Meta:
        db_table = 'jatstype'

class Journal(BaseModel):
    journal = CharField(unique=True)

    class Meta:
        db_table = 'journal'

class Plosarticle(BaseModel):
    doi = TextField(db_column='DOI', unique=True)
    jats_type = ForeignKeyField(db_column='JATS_type_id', rel_model=Jatstype, to_field='id')
    abstract = TextField()
    created_date = DateTimeField()
    journal = ForeignKeyField(db_column='journal_id', rel_model=Journal, to_field='id')
    plostype = ForeignKeyField(db_column='plostype_id', rel_model=Articletype, to_field='id')
    title = TextField()
    word_count = IntegerField()

    class Meta:
        db_table = 'plosarticle'

class Country(BaseModel):
    country = CharField(unique=True)

    class Meta:
        db_table = 'country'

class Correspondingauthor(BaseModel):
    affiliation = ForeignKeyField(db_column='affiliation_id', rel_model=Affiliations, to_field='id')
    corr_author_email = CharField(unique=True)
    country = ForeignKeyField(db_column='country_id', rel_model=Country, to_field='id')
    given_name = TextField(null=True)
    group_name = TextField(null=True)
    surname = TextField(null=True)
    tld = TextField(null=True)

    class Meta:
        db_table = 'correspondingauthor'

class Coauthorplosarticle(BaseModel):
    article = ForeignKeyField(db_column='article_id', rel_model=Plosarticle, to_field='id')
    corr_author = ForeignKeyField(db_column='corr_author_id', rel_model=Correspondingauthor, to_field='id')

    class Meta:
        db_table = 'coauthorplosarticle'



query = (Plosarticle
         .select()
         .join(Coauthorplosarticle)
         .join(Correspondingauthor)
         .join(Country)
         .join(Journal, on=(Plosarticle.journal == Journal.id))
         .where(Country.country == 'France')
         .where(Plosarticle.created_date > '2008-1-1')
         .where(Journal.journal == 'PLOS Computational Biology')
         )

for papers in query:
    print(papers.doi)
print(query.count())

query = (Plosarticle
         .select()
         .join(Coauthorplosarticle)
         .join(Correspondingauthor)
         .join(Affiliations)
         .join(Journal, on=(Plosarticle.journal == Journal.id))
         .where(Country.country == 'France')
         .where(Plosarticle.created_date > '2008-1-1')
         .where(Journal.journal == 'PLOS Computational Biology')
         )
