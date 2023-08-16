import tempfile
import os

# path to the root of allofplos (the package)
ALLOFPLOS_DIR_PATH = os.path.abspath(os.path.dirname(__file__))


# Starter pack of PLOS articles
starterdir = os.path.join(ALLOFPLOS_DIR_PATH, 'starter_corpus')

# Temporary folder for downloading and processing new articles
newarticledir = tempfile.mkdtemp()

# List of uncorrected proof articles to check for updates
(_, uncorrected_proofs_text_list) = tempfile.mkstemp()

def get_corpus_dir():
    """If you want to set the corpus directory, assign the desired path to
    ``os.environ['PLOS_CORPUS']``.
    """
    import os

    return os.path.expanduser(os.environ.get("PLOS_CORPUS", "")) or os.path.join(
        ALLOFPLOS_DIR_PATH, "allofplos_xml"
    )

del os

    

# NB: any packages that you want to expose at the top level, you will need to
# import after creating global variables that they may rely upon
# (e.g., corpusdir)

from .article import Article
from .corpus import Corpus
