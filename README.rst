=========================
 Django FastURL
=========================

This project provides a mechanism for speeding up URL resolution in Django projects.

It provides this speedup in two ways.

* Converting your urlpatterns from a list into an optimized tree.
* Bypassing the regex engine for url fragments that don't use a regex features (the Python regex engine is suprisingly
slow).

In real world testing we have found this to save as much as 12ms per request for items near the end of a list of 750
urlpatterns.

If you don't have at least 100 urlpatterns in your project, you probably shouldn't even be considering installing this.
If your urls are already defined hierarchically then the performance gains will be relatively modest.

Why wouldn't your url's already be defined optimally?  While it is common to define your urls in each app and include
them under a prefix, in some more complex applications the url structure doesn't cleanly map to individual Django
'apps'.  In a large code base the traditional Django method of defining urls in separate files can make it harder to
find where the code for any particular url is defined as one may have to look through multiple urls.py files.

In addition, even if the traditional method of url definition maps well to the project, there are often more levels of
heirarchy than are expressed.  For example:

* ^(?P<id>[^/]+)/$
* ^(?P<id>[^/]+)/action1$
* ^(?P<id>[^/]+)/action2$
* ^(?P<id>[^/]+)/...$
* ^api/(?P<id>[^/]+)/$
* ^api/(?P<id>[^/]+)/action3$
* ^api/(?P<id>[^/]+)/action4$
* ^api/(?P<id>[^/]+)/...$

Can be expressed more optimally in a tree structure as:

* ^(?P<id>[^/]+)
    * ^/$
    * ^action1$
    * ^action2$
    * ^...$
* ^api/(?P<id>[^/]+)
    * ^/$
    * ^action3$
    * ^action4$
    * ^...$


Caveats
=======

Compatible with Django 1.9.  Django 2.0 did some refactoring of the url internals that will require FastURL to be
updated

URL resolution order can change from the list order causing a different view to be returned in rare cases if you have
overlapping urlpatterns (you probably don't).

for example:

* r'^foo/bar/baz$'
* r'^foo/(?P<id>[^/]+)/foop$'
* r'^foo/bar/foop$'

In this case 'foo/bar/foop' would resolve to the 3rd line instead of the 2nd line with django fast-url.


This changes because of the tree structure:

* foo
    * bar
        * baz
        * foop
    * (?P<id>[^/]+)
        * foop


Instructions
------------

In all of your urls.py files replace :code:`from django.conf.urls import url` with :code:`from fasturl import FastUrl as url`

In the master urls.py of your project render the `urlpatterns` after building the `urlpatterns` list.

.. code:: python

    from fasturls import render_fast_urls
    urlpatterns = render_fast_urls(urlpatterns, debug=False)
