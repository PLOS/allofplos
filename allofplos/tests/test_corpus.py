from . import TESTDATADIR
from .. import Corpus
from ..corpus import listdir_nohidden

import random
import pytest

@pytest.fixture
def corpus():
    return Corpus(TESTDATADIR, seed=1000)

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

def test_corpus_contains(corpus):
    assert '10.1371/journal.pbio.2002354' in corpus.dois
    assert '10.1371/journal.pmed.0030132' not in corpus.dois

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
