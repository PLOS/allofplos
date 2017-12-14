==============================
Getting started with allofplos
==============================

allofplos comes with a "starter corpus" so that right after install, you can begin to analyze a set of 122 PLOS articles using the Corpus and Article classes.

    >>> from allofplos import Corpus, Article, starterdir
    >>> corpus = Corpus(starterdir)

You can get a list of the DOIs in the corpus.
    >>> corpus.dois

DOIs are used to initialize an article object. The Article class parses the local XML file and can return a variety of types of information. Here are some examples:

    >>> article = Article(corpus.dois[99])
    >>> article.journal
    'PLOS ONE'
    
    >>> article.type_
    'research-article'

    >>> article.title
    'The Effect of Cluster Size Variability on Statistical Power in Cluster-Randomized Trials'

    >>> article.pubdate
    datetime.datetime(2015, 4, 1, 0, 0)

    >>> article.authors[1]
    {'affiliations': ['Department of Population Medicine, Harvard Medical School/Harvard Pilgrim Health Care Institute, Boston, MA, USA'],
     'author_roles': {'author_notes': ['Analyzed the data',
       'Contributed reagents/materials/analysis tools',
       'Wrote the paper']},
     'author_type': 'contributing',
     'contrib_initials': 'KPK',
     'contrib_type': 'author',
     'editor_type': None,
     'email': None,
     'footnotes': [],
     'given_names': 'Ken P.',
     'group_name': None,
     'ids': [],
     'rid_dict': {'aff': ['aff002']},
     'surname': 'Kleinman'}
