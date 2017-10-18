import os
import re

from plos_corpus import listdir_nohidden, corpusdir
from plos_regex import validate_file

annotation_articles = [article for article in listdir_nohidden(corpusdir) if 'correction' in article]

for article in annotation_articles:
    count = 0
    parts = re.split('\/|\.', article)
    new_filename = os.path.join(corpusdir, 'plos.correction.' + parts[-2] + '.xml')
    if validate_file(new_filename) and new_filename != article:
        os.rename(article, new_filename)
        count += 1
    else:
        pass
print('{} files renamed'.format(count))
