import asyncio
import aiohttp
import requests
import time
import os
import shutil


import lxml.etree as et
from timeit import default_timer

from allofplos.plos_corpus import listdir_nohidden
from allofplos.plos_regex import ALLOFPLOS_DIR_PATH, corpusdir
from allofplos.transformations import URL_TMP, url_to_doi
from allofplos.samples.corpus_analysis import get_all_local_dois
from allofplos import Article

MIN_DELAY = 1.0 # minimum for wait before beginning the next http-request (in s)
MIN_FILES = 9990 # index of the files to start with
NUM_FILES = 10 # how many files do you process

ASYNC_DIRECTORY = os.path.join(ALLOFPLOS_DIR_PATH, "async_test_dir")
SYNC_DIRECTORY = os.path.join(ALLOFPLOS_DIR_PATH, "sync_test_dir")

async def fetch(doi, session):
    """Given a doi, fetch the associated url, using the given asynchronous
    session (a ClientSession) as a context manager.
    
    Returns the article created by transforming the content of the response.
    
    NB: This needs to do better error handling if the url fails or points to an
    invalid xml file.
    """
    url = URL_TMP.format(doi)
    async with session.get(url) as response:
        resp = await response.read()
        article = Article.from_bytes(resp,
                                     directory=ASYNC_DIRECTORY,
                                     write=True,
                                     overwrite=True)
        return article
        
async def fetch_all(dois, max_rate=MIN_DELAY, limit_per_host=3.0):
    """Launch requests for each doi.
    
    This first gets all of the dois passed in as dois.
    
    Then it checks for the existence of dois that are corrected articles that
    should also be downloaded.
    """
    
    tasks = []
    conn = aiohttp.TCPConnector(limit_per_host=limit_per_host)
    async with aiohttp.ClientSession(connector=conn) as session:
        for doi in dois:
            await asyncio.sleep(max_rate) # ensures no more requests than max_rate per second
            task = asyncio.ensure_future(fetch(doi, session))
            tasks.append(task) # create list of tasks
            
        first_batch = await asyncio.gather(*tasks) # gather task responses
        corrected_dois = [article.related_doi 
                          for article in first_batch 
                          if article.type_=="correction"]
        for doi in corrected_dois:
            await asyncio.sleep(max_rate) # ensures no more requests than max_rate per second
            task = asyncio.ensure_future(fetch(doi, session))
            tasks.append(task) # create list of tasks
        
        second_batch = await asyncio.gather(*tasks) # gather task responses
        
    

def sequential_fetch(doi):
    """
    Fetch urls on the basis of the doi being passed in as part of a sequential
    process.

    Returns the article created by transforming the content of the response.

    NB: This needs to do better error handling if the url fails or points to an
    invalid xml file.
    """
    url = URL_TMP.format(doi)
    response = requests.get(url)
    time.sleep(MIN_DELAY)
    article = Article.from_bytes(response.text.encode('utf-8'), 
                                 directory=ASYNC_DIRECTORY,
                                 write=True)
    return article

def demo_sequential(dois):
    """Organises the process of downloading articles associated with dois
    to SYNC_DIRECTORY sequentially.
    
    Side-effect: prints a timer to indicate how long it took.
    """
    recreate_dir(SYNC_DIRECTORY)
    start_time = default_timer()
    for doi in dois:
        start_time_url = default_timer()
        article = sequential_fetch(doi)
        if article.type_ == "correction":
            new_article = sequential_fetch(article.related_doi)

    tot_elapsed = default_timer() - start_time
    print(' TOTAL SECONDS: '.rjust(30, '-') + '{0:5.2f} '. \
        format(tot_elapsed, '\n'))


def demo_async(dois):
    """Organises the process of downloading articles associated with the doi to
    ASYNC_DIRECTORY asynchronous functionality. 
    
    Side-effect: prints a timer to indicate how long it took.
    """
    recreate_dir(ASYNC_DIRECTORY)
    start_time = default_timer()
    loop = asyncio.get_event_loop() # event loop
    future = asyncio.ensure_future(fetch_all(dois)) # tasks to do
    loop.run_until_complete(future) # loop until done
    loop.run_until_complete(asyncio.sleep(0)) 
    loop.close()
    tot_elapsed = default_timer() - start_time
    print(' TOTAL SECONDS: '.rjust(30, '-') + '{0:5.2f} '. \
        format(tot_elapsed, '\n'))
    
def recreate_dir(directory):
    """Removes and recreates the directory.
    """
    if os.path.isdir(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)
        
def main():
    """Main loop for running and comparing the different appraoches.
    """
    
    dois = get_all_local_dois(corpusdir)[MIN_FILES:MIN_FILES+NUM_FILES]
    demo_sequential(dois)
    demo_async(dois)

if __name__ == '__main__':
    main()
