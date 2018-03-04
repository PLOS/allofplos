from . import TESTDATADIR
from .. import Corpus

import random
import pytest

@pytest.fixture
def corpus():
    return Corpus(TESTDATADIR, seed=1000)

def test_corpus_instantiate(corpus):
    assert isinstance(corpus, Corpus)

def test_corpus_len(corpus):
    assert len(corpus) == 5

def test_corpus_iterator(corpus):
    article_dois = {article.doi for article in corpus}
    assert article_dois == {
        '10.1371/annotation/3155a3e9-5fbe-435c-a07a-e9a4846ec0b6',
        '10.1371/journal.pbio.2002399',
        '10.1371/journal.pbio.2002354',
        '10.1371/journal.pone.0185809',
        '10.1371/journal.pbio.2001413',
    }

def test_corpus_random_article(corpus):
    corpus = Corpus(TESTDATADIR, seed=1000)
    article = corpus.random_article
    assert article.doi == "10.1371/journal.pone.0185809"
