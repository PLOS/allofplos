""" This is an example on how to convert the SQLite DB into a class model to
    make queries without using SQL syntax. This example uses peewee as ORM.
    It should be used as a template, the end user could edit it to fit their
    needs.
"""

from peewee import *

# Start of ORM classes creation.

database = SqliteDatabase('starter.db', **{})

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
    jats_type = ForeignKeyField(column_name='JATS_type_id', model=Jatstype, field='id')
    abstract = TextField()
    created_date = DateTimeField()
    journal = ForeignKeyField(column_name='journal_id', model=Journal, field='id')
    plostype = ForeignKeyField(column_name='plostype_id', model=Articletype, field='id')
    title = TextField()
    word_count = IntegerField()

    class Meta:
        db_table = 'plosarticle'

class Country(BaseModel):
    country = CharField(unique=True)

    class Meta:
        db_table = 'country'

class Correspondingauthor(BaseModel):
    affiliation = ForeignKeyField(column_name='affiliation_id', model=Affiliations, field='id')
    corr_author_email = CharField(unique=True)
    country = ForeignKeyField(column_name='country_id', model=Country, field='id')
    given_name = TextField(null=True)
    group_name = TextField(null=True)
    surname = TextField(null=True)
    tld = TextField(null=True)

    class Meta:
        db_table = 'correspondingauthor'

class Coauthorplosarticle(BaseModel):
    article = ForeignKeyField(column_name='article_id', model=Plosarticle, field='id')
    corr_author = ForeignKeyField(column_name='corr_author_id', model=Correspondingauthor, field='id')

    class Meta:
        db_table = 'coauthorplosarticle'

# End of ORM classes creation.

# Query the starter database to retrieve all paper published in the journal
# PLOS Computational Biology, since 2008 with a corresponding author from
# France.
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

# Get how many papers are returned
print("Papers: {}".format(query.count()))

# Get the DOIs of all the papers found with the query
print("DOIs:")
for papers in query:
    print(papers.doi)
