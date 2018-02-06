import datetime
import os
import tarfile
from zipfile import ZipFile, BadZipFile

import requests
from tqdm import tqdm

from .. import get_corpus_dir

# Variables needed
ZIP_ID = '0B_JDnoghFeEKLTlJT09IckMwOFk'
METADATA_ID = '0B_JDnoghFeEKQUhKWXBOVy1aTlU'
LOCAL_ZIP = 'allofplos_xml.zip'
ZIP_METADATA = 'zip_info.txt'
time_formatting = "%Y_%b_%d_%Hh%Mm%Ss"
min_files_for_valid_corpus = 200000
TEST_ZIP_ID = '12VomS72LdTI3aYn4cphYAShv13turbX3'
LOCAL_TEST_ZIP = 'sample_corpus.zip'
GDRIVE_URL = "https://docs.google.com/uc?export=download"


def download_file_from_google_drive(id, filename, directory=None,
                                    file_size=None):
    """
    General method for downloading from Google Drive.
    Doesn't require using API or having credentials
    :param id: Google Drive id for file (constant even if filename change)
    :param filename: name of the zip file
    :param directory: directory where to download the zip file, defaults to get_corpus_dir
    :param file_size: size of the file being downloaded
    :return: None
    """
    if directory is None:
        directory = get_corpus_dir()

    file_path = os.path.join(directory, filename)
    extension = os.path.splitext(file_path)[1]

    # check for existing incomplete zip download. Delete if invalid zip.
    if os.path.isfile(file_path) and extension.lower() == '.zip':
        try:
            zip_file = ZipFile(file_path)
            if zip_file.testzip():
                os.remove(file_path)
                print("Deleted corrupted previous zip download.")
            else:
                pass
        except BadZipFile as e:
            os.remove(file_path)
            print("Deleted invalid previous zip download.")

    else:
        pass

    if not os.path.isfile(file_path):
        session = requests.Session()

        response = session.get(GDRIVE_URL, params={'id': id}, stream=True)
        token = get_confirm_token(response)

        if token:
            params = {'id': id, 'confirm': token}
            response = session.get(GDRIVE_URL, params=params, stream=True)
        save_response_content(response, file_path, file_size=file_size)
    return file_path


def get_confirm_token(response):
    """
    Part of keep-alive method for downloading large files from Google Drive
    Discards packets of data that aren't the actual file
    :param response: session-based google query
    :return: either datapacket or discard unneeded data
    """
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None


def save_response_content(response, download_path, file_size=None):
    """
    Saves the downloaded file parts from Google Drive to local file
    Includes progress bar for download %
    :param response: session-based google query
    :param download_path: path to local zip file
    :param file_size: size of the file being downloaded
    :return: None
    """
    CHUNK_SIZE = 32768
    # for downloading zip file
    if os.path.basename(download_path) == LOCAL_ZIP:
        with open(download_path, "wb") as f:
            size = file_size
            pieces = round(size / CHUNK_SIZE)
            with tqdm(total=pieces) as pbar:
                for chunk in response.iter_content(CHUNK_SIZE):
                    pbar.update(1)
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
    # for downloading zip metadata text file
    else:
        with open(download_path, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)


def get_zip_metadata(method='initial'):
    """
    Gets metadata txt file from Google Drive, that has info about zip file
    Used to get the file name, as well as byte size for progress bar
    Includes progress bar for download %
    :param method: boolean if initializing the PLOS Corpus (defaults to True)
    :return: tuple of data about zip file: date zip created, zip size, and location of metadata txt file
    """
    if method == 'initial':
        metadata_path = download_file_from_google_drive(METADATA_ID, ZIP_METADATA)
    with open(metadata_path) as f:
        zip_stats = f.read().splitlines()
    zip_datestring = zip_stats[0]
    zip_date = datetime.datetime.strptime(zip_datestring, time_formatting)
    zip_size = int(zip_stats[1])
    return zip_date, zip_size, metadata_path


def unzip_articles(file_path,
                   extract_directory=None,
                   filetype='zip',
                   delete_file=True
                   ):
    """
    Unzips zip file of all of PLOS article XML to specified directory
    :param file_path: path to file to be extracted
    :param extract_directory: directory where articles are copied to
    :param filetype: whether a 'zip' or 'tar' file (tarball), which use different decompression libraries
    :param delete_file: whether to delete the compressed archive after extracting articles
    :return: None
    """
    if extract_directory is None:
        extract_directory = get_corpus_dir()

    os.makedirs(extract_directory, exist_ok=True)

    if filetype == 'zip':
        with ZipFile(file_path, "r") as zip_ref:
            tqdm.write("Extracting zip file...")
            for article in tqdm(zip_ref.namelist()):
                zip_ref.extract(article, path=extract_directory)
            tqdm.write("Extraction complete.")
    elif filetype == 'tar':
        tar = tarfile.open(file_path)
        print("Extracting tar file...")
        tar.extractall(path=extract_directory)
        tar.close()
        print("Extraction complete.")

    if delete_file:
        os.remove(file_path)
