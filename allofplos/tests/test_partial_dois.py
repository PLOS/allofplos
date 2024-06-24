from .. import Corpus, Article, starterdir
from ..plos_regex import validate_partial_doi, validate_doi
from ..transformations import partial_to_doi, doi_to_partial

import pytest


@pytest.fixture
def corpus():
    return Corpus(starterdir, seed=1000)


@pytest.fixture
def test_article():
    return Article('10.1371/journal.pone.0040259', directory=starterdir)


@pytest.fixture
def test_doi():
    return '10.1371/journal.pone.0040259'


@pytest.fixture
def test_partial_doi():
    return 'pone.0040259'


def test_partial_doi_regex(test_partial_doi):
    assert validate_partial_doi(test_partial_doi)
    assert not validate_partial_doi(' pone.0040259')
    assert not validate_partial_doi('pone.0040259 ')


def test_partial_doi_transform(test_doi, test_partial_doi):
    partial_doi = doi_to_partial(test_doi)
    assert partial_doi == test_partial_doi


def test_doi_transform(test_partial_doi, test_doi):
    doi = partial_to_doi(test_partial_doi)
    assert validate_doi(doi)
    assert doi == test_doi


def test_partial_doi_method_article(test_partial_doi, test_article):
    article = Article.from_partial_doi(test_partial_doi, directory=starterdir)
    assert article == test_article


def test_partial_doi_method_corpus(corpus, test_article, test_partial_doi):
    article = corpus[test_partial_doi]
    assert article == test_article
