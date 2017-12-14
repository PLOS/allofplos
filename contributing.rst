Telegram channel for Allofplos
------------------------------

There is a public Telegram channel (`allofplos 
<https://t.me/joinchat/CjgRKRKN_bnL4cBu8RisZw>`_) where the developers hang out to chat about Allofplos. You may use this channel to make a quiestion about development with allofplos. 


Installing files for editing
----------------------------

Use this command to install the project in a way you can make edits and this edits be reflected in the installed version (this is the "development mode")

    pip install -U -e DIRECTORY/allofplos


Thing to check before doing a release
-------------------------------------

* Run the tests
* Version number is stated in the setup.py file
* HISTORY.txt file with the last change at the beginning

Making a release
----------------

Delete previous packages from dist directory::

    rm dist/*.*

Run bdist_wheel::

    python setup.py bdist_wheel --universal

Upload with twine::

    twine upload dist/*

(you will need pypi credentials to do the upload)
