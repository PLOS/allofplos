from . import TESTDATADIR
from .. import Corpus, starterdir
from ..article_class import Article
from ..corpus import listdir_nohidden

import random
import pytest
import os

@pytest.fixture
def corpus():
    return Corpus(TESTDATADIR, seed=1000)

@pytest.fixture
def yes_article():
    return Article('10.1371/journal.pbio.2002354', directory=TESTDATADIR)
    
@pytest.fixture
def no_article():
    return Article('10.1371/journal.pmed.0030132', directory=starterdir)

def test_corpus_instantiate(corpus):
    assert isinstance(corpus, Corpus)

def test_corpus_len(corpus):
    assert len(corpus) == 5

def test_corpus_iter_(corpus):
    article_dois = {article.doi for article in corpus}
    assert article_dois == {
        '10.1371/annotation/3155a3e9-5fbe-435c-a07a-e9a4846ec0b6',
        '10.1371/journal.pbio.2002399',
        '10.1371/journal.pbio.2002354',
        '10.1371/journal.pone.0185809',
        '10.1371/journal.pbio.2001413',
    }

def test_corpus_contains_article(corpus, no_article, yes_article):
    assert yes_article in corpus
    assert no_article not in corpus

def test_corpus_contains_doi(corpus, no_article, yes_article):
    assert yes_article.doi in corpus
    assert no_article.doi not in corpus

def test_corpus_contains_filepath(corpus, no_article, yes_article):
    ## check for filepath, which is currently called filename on Article
    assert yes_article.filename in corpus
    assert no_article.filename not in corpus

def test_corpus_contains_file(corpus, no_article, yes_article):
    ## check for filename, which is currently unavailable on Article
    assert os.path.basename(yes_article.filename) in corpus
    assert os.path.basename(no_article.filename) not in corpus

def test_corpus_random_article(corpus):
    article = corpus.random_article
    assert article.doi == "10.1371/journal.pone.0185809"

def test_corpus_indexing(corpus):
    assert corpus["10.1371/journal.pbio.2001413"] == corpus[0]
    assert next(corpus[:1]).doi == "10.1371/journal.pbio.2001413"
    assert next(corpus[1:]).doi != "10.1371/journal.pbio.2001413"

def test_iter_file_doi(corpus):
    expected = {
     'journal.pbio.2001413.xml': '10.1371/journal.pbio.2001413',
     'journal.pbio.2002354.xml': '10.1371/journal.pbio.2002354',
     'journal.pbio.2002399.xml': '10.1371/journal.pbio.2002399',
     'journal.pone.0185809.xml': '10.1371/journal.pone.0185809',
     'plos.correction.3155a3e9-5fbe-435c-a07a-e9a4846ec0b6.xml': 
         '10.1371/annotation/3155a3e9-5fbe-435c-a07a-e9a4846ec0b6',
     }
    assert expected == {f:doi for f, doi in corpus.iter_file_doi} 


def test_filepaths(corpus):
    assert set(corpus.filepaths) == set(listdir_nohidden(TESTDATADIR))

def test_files(corpus):
    annote_file = 'plos.correction.3155a3e9-5fbe-435c-a07a-e9a4846ec0b6.xml'
    assert annote_file in corpus.files
    assert 'journal.pcbi.0030158.xml' not in corpus.files
