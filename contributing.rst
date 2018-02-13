How to install for developing
-----------------------------

Clone the repository with::

    git clone https://github.com/PLOS/allofplos.git

Change to the directory where the code is downloaded::

    cd allofplos

Provided that you are in the allofplos directory, install it with::

    pip install -U -e .


Thing to check before doing a release
-------------------------------------

* Run the tests
* Version number is stated in the setup.py file
* HISTORY.txt file with the last change at the beginning

Making a release
----------------
Remove untracked files::
	git clean -xfdi

Delete previous packages from dist directory::

    rm dist/*.*

Run bdist_wheel::

    python setup.py bdist_wheel --universal

Upload with twine::

    twine upload dist/*

(you will need pypi credentials to do the upload)
