How to install for developing
-----------------------------

Clone the repository with::

    git clone https://github.com/PLOS/allofplos.git

Change to the directory where the code is downloaded::

    cd allofplos

Provided that you are in the allofplos directory, install it with::

    pip install -U -e .

How to run the tests
--------------------

``allofplos`` uses ``pytest`` to run its tests. Run ``pip install -e .[test]``
from the top level of the directory, this will install pytest as well as any
other testing dependencies.

Once you have ``pytest`` installed, from inside the allofplos directory, run:

``(allofplos)$ pytest``

It should return something like:

.. code::
  
  collected 20 items

  allofplos/tests/test_corpus.py ............                       [ 60%]
  allofplos/tests/test_unittests.py ........                        [100%]

  ==================== 20 passed in 0.36 seconds =========================

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
