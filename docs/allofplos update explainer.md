# How corpus updates work
This describes how and why the set of functions in `plos.corpus.download_check_and_move()` work.

## Why update the corpus?
Having 'all of PLOS' on your local computer means hitting a constantly moving target. Five times a week, new articles are published. That means if you download the allofplos zip file on Monday and extract it to your local corpus directory, on Tuesday there will already be new articles available, probably 50-100 more, and your local copy will be out-of-date.

Additionally, sometimes the content of existing articles may change. Articles can be republished for a number of reasons, either as part of an established workflow (uncorrected proofs/early versions of articles, getting replaced in-place by the final version of record or VOR), or as a one-off (as part of an amendment: meaning, a correction, retraction, or expression of concern is issued). When the article XML itself changes, you want to always have the latest version as it will be the most correct.

## allofplos: DOIs and article files
Every PLOS article has a unique digital object identifier (DOI), as well as a number of article assets: a PDF version, an XML version, and additional files and figures. allofplos has a single XML file for every article, with a file naming convention using part of the DOI. All PLOS DOIs begin with "10.1371/" and that is omitted from the filename. For example, the PLOS ONE article with a DOI of `10.1371/journal.pone.0187394` is associated with a local file in the corpus directory of `journal.pone.0187394.xml`.

## Step 1: Compare local list of DOIs to all PLOS DOIs
PLOS has a search API using Solr by Apache, which includes information about every article PLOS has published, and is always up-to-date. The function `plos_corpus.get_all_solr_dois()` queries the search API for all valid PLOS DOIs and returns a list of every article listed on Solr. This can be considered the canonical list of PLOS article DOIs.
Thus, the first step of the update is to establish which newly published articles are not yet part of the local XML corpus. The difference between the solr set of DOIs and the local set of DOIs is calculated by `plos_corpus.get_dois_needed_list()`, which provides the list of DOIs to download.

## Step 2: Download new articles to temp directory
The first phase of `plos_corpus.download_check_and_move()` takes the list of DOIs from step 1 and downloads the accompanying article XML files into the temporary download directory. It then runs a series of checks.

At this point, tempdir only contains new articles not found in corpusdir. 

### Check 1a: are any newly downloaded articles in tempdir 'amendment' types?

As mentioned earlier, there are several reasons why an already published article would have its XML replaced with a new version. One of those reasons is the article amendment process: when an article is issued a correction, retraction, or statement of concern. First, every new tempdir article has its type checked to see if it is an amendment article type (`self.amendment`). If so, any `<related-article>` DOI fields (`self.related_dois`) are added to the list of *amended* articles.

### Check 1b: are any of the amended articles updated?
Depending on how long ago the `plos_corpus` update was run, those amended articles may also be in the tempdir. However they are likely to be in the corpusdir, where the script checks first. It compares the local to remote version of the XML by passing the online version from `self.url` and the local version at `self.filename` into lxml etree and checking whether they are the same unicode string. If they are, it skips over the article. If they are different, the script adds the new version of the amended article to the tempdir.

At this point, tempdir contains both brand-new articles and new versions of older articles which have been amended.

### Check 2a: are any of the uncorrected proofs updated?
It's time-consuming to check every article in corpusdir for whether it's an uncorrected proof, i.e., the early version of an article posted online before the final version (as ascertained by `self.proof` in the Article class). Therefore a text list, `uncorrected_proofs_list.txt`, is used to store the list of DOIs of uncorrected proofs. The second check is pulling this text list into memory and checking each one of those articles (almost certainly in corpusdir) for whether a version of record (VOR) has been issued (by checking the remote version at `self.remote_xml` for the field in `self.proof`). If it is a VOR, that new version is downloaded to tempdir and the uncorrected proof list in memory has that DOI removed. 

At this point, the tempdir contains brand-new articles, new versions of amended articles, and new VORs for existing uncorrected proofs.

### Check 2b: are any of the new tempdir articles uncorrected proofs?
Each article in tempdir is checked for whether `self.proof` indicates an uncorrected proof. If so, it is added to the list in memory of uncorrected proofs. After each tempdir article has been checked, the list of uncorrected proofs in memory is written back to the text file, having both removed DOIs for articles that now have a VOR in tempdir as well as adding newly downloaded uncorrected proofs.

## Step 3: move tempdir articles into corpusdir
Now that all of the new articles in tempdir have been processed, and amended articles and uncorrected proofs have their new versions in tempdir, all new articles are moved into corpusdir, replacing any old versions of articles that may have previously existed there. Corpusdir is now up-to-date!

