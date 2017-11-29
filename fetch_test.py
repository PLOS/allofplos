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

begin_time = default_timer()

ASYNC_DIRECTORY = os.path.join(ALLOFPLOS_DIR_PATH, "async_test")
MIN_FILES = 9990
NUM_FILES = 10

async def fetch(url, session):
    """Fetch a url, using specified ClientSession."""
    fetch.start_time[url] = default_timer()
    async with session.get(url) as response:
        resp = await response.read()
        article = Article.from_bytes(resp,
                                     directory=ASYNC_DIRECTORY,
                                     write=True,
                                     overwrite=True)
        now = default_timer()
        elapsed = now - fetch.start_time[url]
        # print('{0:5.2f} {1:30}{2:5.2} '.format(now, url, elapsed))
        return article
        
async def fetch_all(dois, max_rate=1.0, limit_per_host=3.0):
    """Launch requests for all web pages."""
    tasks = []
    fetch.start_time = dict() # dictionary of start times for each url
    conn = aiohttp.TCPConnector(limit_per_host=limit_per_host)
    async with aiohttp.ClientSession(connector=conn) as session:
        for doi in dois:
            await asyncio.sleep(max_rate) # ensures no more requests than max_rate per second
            task = asyncio.ensure_future(
                fetch(URL_TMP.format(doi), session))
            tasks.append(task) # create list of tasks
            
        first_batch = await asyncio.gather(*tasks) # gather task responses
        corrected_dois = [article.related_doi 
                          for article in first_batch 
                          if article.type_=="correction"]
        for doi in corrected_dois:
            await asyncio.sleep(max_rate) # ensures no more requests than max_rate per second
            task = asyncio.ensure_future(
                fetch(URL_TMP.format(doi), session))
            tasks.append(task) # create list of tasks
        
        second_batch = await asyncio.gather(*tasks) # gather task responses
        
    
    # -------------- TOTAL SECONDS: 178.59        

def sequential_fetch(doi):
    "Fetch individual web pages as part of a sequence"
    url = URL_TMP.format(doi)
    response = requests.get(url)
    time.sleep(1)
    article = Article.from_bytes(response.text.encode('utf-8'), 
                                 directory=ASYNC_DIRECTORY,
                                 write=True)
    return article

def demo_sequential(dois):
    """Fetch list of web pages sequentially."""
    handle_dir()
    start_time = default_timer()
    for doi in dois:
        start_time_url = default_timer()
        article = sequential_fetch(doi)
        now = default_timer()
        elapsed = now - start_time_url
        if article.type_ == "correction":
            new_article = sequential_fetch(article.related_doi)
            
        # print('{0:5.2f} {1:30}{2:5.2f} '.format(now, url, elapsed)) 
    
    tot_elapsed = default_timer() - start_time
    print(' TOTAL SECONDS: '.rjust(30, '-') + '{0:5.2f} '. \
        format(tot_elapsed, '\n'))


def demo_async(dois):
    handle_dir()
    start_time = default_timer()
    loop = asyncio.get_event_loop() # event loop
    future = asyncio.ensure_future(fetch_all(dois)) # tasks to do
    loop.run_until_complete(future) # loop until done
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()
    tot_elapsed = default_timer() - start_time
    print(' TOTAL SECONDS: '.rjust(30, '-') + '{0:5.2f} '. \
        format(tot_elapsed, '\n'))
        
def main():
    
    dois = get_all_local_dois(corpusdir)[MIN_FILES:MIN_FILES+NUM_FILES]
    
    demo_sequential(dois)
    demo_async(dois)

def handle_dir():
    if os.path.isdir(ASYNC_DIRECTORY):
        shutil.rmtree(ASYNC_DIRECTORY)
    os.makedirs(ASYNC_DIRECTORY, exist_ok=True)
if __name__ == '__main__':
    main()
