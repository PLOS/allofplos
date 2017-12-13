import os

# path to the root of allofplos (the package)
ALLOFPLOS_DIR_PATH = os.path.abspath(os.path.dirname(__file__))

# Main directory for the corpus of article XML files
corpusdir = os.path.join(ALLOFPLOS_DIR_PATH, 'allofplos_xml')

# Starter pack of PLOS articles
starterdir = os.path.join(ALLOFPLOS_DIR_PATH, 'starter_corpus')

# Temporary folder for downloading and processing new articles
newarticledir = os.path.join(ALLOFPLOS_DIR_PATH, 'new_plos_articles')

del os

# NB: any packages that you want to expose at the top level, you will need to
# import after creating global variables that they may rely upon
# (e.g., corpusdir)

from .article_class import Article
