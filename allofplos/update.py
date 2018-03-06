import os

from . import get_corpus_dir, newarticledir, uncorrected_proofs_text_list
from .corpus.plos_corpus import (create_local_plos_corpus, get_dois_needed_list, download_check_and_move,
                                 min_files_for_valid_corpus)


def main():
    """
    Entry point for the program. This is used when the program is used as a
    standalone script
    :return: None
    """
    directory = get_corpus_dir()

    # Step 0: Initialize first copy of repository
    try:
        corpus_files = [name for name in os.listdir(directory) if os.path.isfile(
                        os.path.join(directory, name))]
    except FileNotFoundError:
        corpus_files = []
    if len(corpus_files) < min_files_for_valid_corpus:
        print('Not enough articles in {}, re-downloading zip file'.format(directory))
        # TODO: check if zip file is in top-level directory before downloading
        create_local_plos_corpus()

    # Step 1: Query solr via URL and construct DOI list
        # Filtered by article type & scheduled for the last 14 days.
        # Returns specific URL query & the number of search results.
        # Parses the returned dictionary of article DOIs, removing common leading numbers, as a list.
        # Compares to list of existing articles in the PLOS corpus folder to create list of DOIs to download.
    print("Checking for new articles...")
    dois_needed_list = get_dois_needed_list()

    # Step 2: Download new articles
        # For every doi in dois_needed_list, grab the accompanying XML from journal pages
        # If no new articles, don't run any other cells
        # Check if articles are uncorrected proofs
        # Check if amended articles linked to new amendment articles are updated
        # Merge new XML into folder
        # If need to bulk download, please start here:
        # https://drive.google.com/open?id=0B_JDnoghFeEKLTlJT09IckMwOFk
    download_check_and_move(dois_needed_list,
                            uncorrected_proofs_text_list,
                            tempdir=newarticledir,
                            destination=get_corpus_dir()
                            )
    return None


if __name__ == "__main__":
    main()
