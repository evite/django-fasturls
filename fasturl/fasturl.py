import re
from collections import OrderedDict
from django.conf.urls import url as django_url, include
from django.core.urlresolvers import RegexURLResolver, RegexURLPattern
from django.utils.encoding import force_text
import logging

# Using FastUrl has a couple of caveats:
# 1. FastUrl tries to keep the resolution order the same as declared, but we cannot guarantee that the order will
#    be exactly the same which could cause the wrong view to be returned if you have urlpatterns that overlap.
# 2. Detection of regexes within urlpatterns is very ad-hock, it would be easy to deliberately cause it to fail, but
#    in practice it should cover most cases.  Any errors should occur during url building rather than at resolution time

# Usage:
#  Build your urlpatterns using 'FastUrl' instead of 'url' and then rebuild your urlpatterns with
#    urlpatterns = render_fast_urls(urlpatterns)


class StartsWithResolver(RegexURLResolver):
    """
    Python regexs are pretty slow, so this class checks if the string looks like it matches before
    passing it through to the regular resolver class
    """
    def __init__(self, regex, view, kwargs=None):
        urlconf_module, app_name, namespace = view
        super(StartsWithResolver, self).__init__(regex, urlconf_module, kwargs, app_name=app_name, namespace=namespace)
        self.pattern = regex
        if self.pattern[0] == "^":
            self.pattern = self.pattern[1:]
            self.passthrough = False
            for char in "$()[]<>*?\\":
                if char in self.pattern:
                    self.passthrough = True
        else:
            self.passthrough = True

    def resolve(self, path):
        if not self.passthrough:
            path = force_text(path)  # path may be a reverse_lazy object
            if not path.startswith(self.pattern):
                return False
        return super(StartsWithResolver, self).resolve(path)


class FastUrl(object):
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def add_to_tree(self, tree):
        # This does some super ad-hock detection of regex patterns and tries to re-join any regexes that
        # were split in the middle
        words = re.split('/', self._args[0])

        for i in range(len(words) - 2, 0, -1):
            if words[i] and words[i + 1] and (words[i][-1] == "^" or words[i + 1][0] == "?"):
                words = words[:i] + [words[i] + "/" + words[i + 1]] + words[i + 2:]

        new_words = []
        parens_index = -1
        parens = 0
        for i, word in enumerate(words):
            if "(" in words[i]:
                if parens == 0:
                    parens_index = i
                parens += word.count('(')
            if "[" in words[i]:
                if parens == 0:
                    parens_index = i
                parens += word.count('[')
            if ")" in words[i]:
                parens -= word.count(')')
            if "]" in words[i]:
                parens -= word.count(']')
            if parens_index < 0:
                new_words.append(word)
            elif parens == 0:
                new_words.append('/'.join(words[parens_index:i+1]))
                parens_index = -1
        if parens_index != -1:
            raise RuntimeError("Mismatched parentheses in urlpattern {}".format(self._args[0]))
        words = new_words
        if words[-1] in ("?", "?$", "$"):
            words = words[:-2] + [words[-2] + "/" + words[-1]]
        entry = tree
        for word in words[:-1]:
            if not entry.get(word):
                entry[word] = OrderedDict()
            entry = entry[word]

        processed_include = False

        # For include(...) processing. we add the urls to the tree instead of instantiating a RegexURLResolver
        if isinstance(self._args[1], (list, tuple)):
            urlconf_module, app_name, namespace = self._args[1]
            if not app_name and not namespace:
                processed_include = True
                word = words[-1]
                if not entry.get(word):
                    entry[word] = OrderedDict()
                for url in urlconf_module.urlpatterns:
                    _add_url_to_tree(entry, url)

        if not processed_include:
            if words[-1] in entry:
                logging.error("Duplicate entry for urlpattern {}".format(self._args[0]))
            entry[words[-1]] = (self._args, self._kwargs)


def _is_django_regex(ob):
    if isinstance(ob, RegexURLPattern) or isinstance(ob, RegexURLResolver):
        return True
    return False


def _add_url_to_tree(tree, url):
    if isinstance(url, FastUrl):
        url.add_to_tree(tree)
    if _is_django_regex(url):
        tree[('djangourl', _add_url_to_tree.django_urls)] = url
        _add_url_to_tree.django_urls += 1


_add_url_to_tree.django_urls = 0  # counter for django only urls

merged_count = 0


def _merge_single_children(tree):
    if not isinstance(tree, dict):
        return tree

    new_tree = OrderedDict()
    for path, param in tree.items():
        if isinstance(param, dict):
            child = _merge_single_children(param)
            if isinstance(child, dict) and len(child) == 1:
                new_tree[path + '/' + child.keys()[0]] = child.values()[0]
                _merge_single_children.count += 1
            else:
                new_tree[path] = _merge_single_children(param)
        else:
            new_tree[path] = param
    return new_tree


_merge_single_children.count = 0


def render_fast_urls(urls, debug=False):
    url_tree = OrderedDict()

    # Expand the url list into the tree structure
    for url in urls:
        _add_url_to_tree(url_tree, url)

    # Merge any entries with only a single child
    url_tree = _merge_single_children(url_tree)

    # Render the tree back into a list
    def render_tree(tree):
        new_urls = []
        for path, param in tree.items():
            if _is_django_regex(param):
                new_urls.append(param)
            else:
                if path and path[0] is not "^":
                    path = "^" + path
                if not path:
                    path = "^$"
                if isinstance(param, dict):
                    new_urls.append(StartsWithResolver(path + "/", include(render_tree(param))))
                else:
                    p = (path,) + param[0][1:]
                    new_urls.append(django_url(*p, **param[1]))
        return new_urls

    urlpatterns = render_tree(url_tree)

    if debug:
        _print_tree(url_tree, 0)
        print ("FastUrl generated {} top level url patterns from {} total urls".format(len(urlpatterns), _count_tree(url_tree)))
        print ("There were {} normal django urls.".format(_add_url_to_tree.django_urls))
        print ("{} branches were merged".format(_merge_single_children.count))

    return urlpatterns


def _print_tree(tree, indent = 0):
    if not isinstance(tree, dict):
        return
    for key in tree.keys():
        print (" " * indent + str(key))
        _print_tree(tree[key], indent +2)


def _count_tree(tree):
    if not isinstance(tree, dict):
        return 1
    total = 0
    for key in tree.keys():
        total += _count_tree(tree[key])
    return total
