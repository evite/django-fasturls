from unittest import TestCase
from datetime import datetime

from django.conf import settings
from django.conf.urls import url
from django.core.urlresolvers import RegexURLResolver
from fasturl.fasturl import render_fast_urls, StartsWithResolver, FastUrl, _merge_single_children


def xpermiations(count, wordlist):
    for word in wordlist:
        if count > 1:
            for words in xpermiations(count - 1, wordlist):
                yield [word] + words
        else:
            yield [word]


def gen_view(wordlist):
    def view(*args, **kwargs):
        return "-".join(wordlist)
    return view


def args_view(*args, **kwargs):
    return (args, kwargs)


settings.configure(DEBUG=True)


class FastUrlTestCase(TestCase):
    def test_regexes(self):
        tough_patterns = [r'^a/b/c$',
                          r'^foo/bar/baz(/(?P<message_id>\w+)\.(?P<fragment_type>\w+)\.(?P<msg_format>\w+))?/?',
                          ]
        tough_requests = ['/a/b/c',
                          '/foo/bar/baz/asdf.qwerty.hjkl/']

        fast_urls = []
        django_urls = []
        for urlpattern in tough_patterns:
            fast_urls.append(FastUrl(urlpattern, args_view))
            django_urls.append(url(urlpattern, args_view))

        fast_urls = render_fast_urls(fast_urls, debug=False)
        fast_resolver = StartsWithResolver("^/", (fast_urls, "fast", ""))

        django_resolver = RegexURLResolver("^/", django_urls)

        for request in tough_requests:
            fast_results = fast_resolver.resolve(request)
            django_results = django_resolver.resolve(request)
            self.assertEqual(fast_results.func(*fast_results.args, **fast_results.kwargs),
                             django_results.func(*django_results.args, **django_results.kwargs))

    def test_lookup_speed(self):
        wordlist = ['lorem', 'ipsum', 'delorean', 'time-traveling', 'hovering', 'skateboards', 'biff', 'X([^/]+)']
        resolve_wordlist = ['lorem', 'ipsum', 'delorean', 'time-traveling', 'hovering', 'skateboards', 'biff', 'Xasdf']
        url_depth = 3
        fast_urls = []
        django_urls = []
        for words in xpermiations(url_depth, wordlist):
            fast_urls.append(FastUrl("/".join(words), gen_view(words), name="-".join(words)))
            django_urls.append(url("/".join(words), gen_view(words), name="-".join(words)))

        fast_urls = render_fast_urls(fast_urls, debug=False)

        fast_resolver = StartsWithResolver("^/", (fast_urls, "fast", ""))

        django_resolver = RegexURLResolver("^/", django_urls)

        start_time = datetime.now()
        for words in xpermiations(url_depth, resolve_wordlist):
            resolved = fast_resolver.resolve("/" + '/'.join(words))
            self.assertIsNotNone(resolved, "couldn't resolve /" + '/'.join(words))
            self.assertEqual(resolved[0]().replace('([^/]+)', 'asdf'), "-".join(words))
        fast_time = datetime.now() - start_time

        start_time = datetime.now()
        for words in xpermiations(url_depth, resolve_wordlist):
            resolved = django_resolver.resolve("/" + '/'.join(words))
            self.assertIsNotNone(resolved, "couldn't resolve /" + '/'.join(words))
            self.assertEqual(resolved[0]().replace('([^/]+)', 'asdf'), "-".join(words))
        django_time = datetime.now() - start_time

        #print "Django resolver ({})  FastUrl resolver ({})    Speedup: {}".format(django_time, fast_time, django_time.total_seconds() / fast_time.total_seconds())

        self.assertGreater(django_time, fast_time * 2, "FastUrl should be at least twice as fast")

    def test_merge_single_children(self):
        test_tree = {"foo": {"bar": (("baz", "some_view"), {})},
                     "foo3": {"bar": {"baz": (("foop", "some_view"), {})}},
                     "foo2": {"bar2": (("baz", "some_view"), {}),
                              "bar3": (("baz", "some_view"), {}),
                              },
                     "a": {"b": {"c": {"d1": (("baz", "some_view"), {}),
                                       "d2": (("baz", "some_view"), {})
                                       }}}
                     }
        expected_results = {"foo/bar": (("baz", "some_view"), {}),
                            "foo3/bar/baz": (("foop", "some_view"), {}),
                            "foo2": {"bar2": (("baz", "some_view"), {}),
                                     "bar3": (("baz", "some_view"), {}),
                                    },
                            "a/b/c": {"d1": (("baz", "some_view"), {}),
                                      "d2": (("baz", "some_view"), {})
                                     }
                            }

        merged_tree = _merge_single_children(test_tree)
        self.assertEqual(merged_tree, expected_results)




