import hashlib

BLOCKSIZE = 65536
hasher = hashlib.sha256()


def hash_file(fname):
    """ Create a SHA-256 hash for an article file in the corpus directory.

    Used in `Corpus().hashtable()`. Takes a full filepath.
    :return: SHA-256 hexcode for a file
    """
    with open(fname, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
        file_hash = hasher.hexdigest()

    return file_hash
