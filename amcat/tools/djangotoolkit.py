###########################################################################
#          (C) Vrije Universiteit, Amsterdam (the Netherlands)            #
#                                                                         #
# This file is part of AmCAT - The Amsterdam Content Analysis Toolkit     #
#                                                                         #
# AmCAT is free software: you can redistribute it and/or modify it under  #
# the terms of the GNU Affero General Public License as published by the  #
# Free Software Foundation, either version 3 of the License, or (at your  #
# option) any later version.                                              #
#                                                                         #
# AmCAT is distributed in the hope that it will be useful, but WITHOUT    #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or   #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public     #
# License for more details.                                               #
#                                                                         #
# You should have received a copy of the GNU Affero General Public        #
# License along with AmCAT.  If not, see <http://www.gnu.org/licenses/>.  #
###########################################################################

"""
Useful functions for dealing with django (models)x
"""

from __future__ import unicode_literals, print_function, absolute_import

import collections
from django.http import QueryDict
import re
import time
import json
import urllib
import logging; LOG = logging.getLogger(__name__)

from django.db.models.fields.related import ForeignKey, OneToOneField, ManyToManyField
from django.db import models
from django.db import connections
from contextlib import contextmanager


from amcat.tools.table.table3 import ObjectTable, SortedTable

def to_querydict(d, mutable=False):
    """Convert a normal dictionary to a querydict. The dictionary can have lists as values,
    which are interpreted as multiple arguments for one url-parameter."""
    # querydict cannot handle unicode, so utf-8 encode unicode content first
    # TODO: this stinks
    def encode(s):
        if isinstance(s, list):
            return map(encode, s)
        elif isinstance(s, unicode):
            return s.encode("utf-8")
        else:
            return s
            
    d = {k : encode(v) for (k,v) in d.iteritems()}
    return QueryDict(urllib.urlencode(d, True), mutable=mutable)

def from_querydict(d):
    """Convert a QueryDict to a normal dictionary with lists as values."""
    return dict(d.iterlists())

def db_supports_distinct_on(db='default'):
    """
    Return a boolean indicating whether this database supports DISTINCT ON.
    
    @param db: database to consider
    @type db: str
    """
    return connections[db].features.can_distinct_on_fields


def distinct_args(*fields):
    """
    return fields if the db supports distinct on, otherwise an empty list
    Intended usage: qs.distinct(*distinct_args(field1, field2))
    This will run distinct(field1, field2) if supported, otherwise just distinct()
    """
    return fields if db_supports_distinct_on() else []

def get_related(appmodel):
    """Get a sequence of model classes related to the given model class"""
    # from modelviz.py:222 vv
    for field in appmodel._meta.fields:
        if isinstance(field, (ForeignKey, OneToOneField)):
            yield field.related.parent_model
    if appmodel._meta.many_to_many:
        for field in appmodel._meta.many_to_many:
            if isinstance(field, ManyToManyField) and getattr(field, 'creates_table', False):
                yield field.related.parent_model

def get_all_related(modelclasses):
    """Get all related model classes from the given model classes"""
    for m in modelclasses:
        for m2 in get_related(m):
            yield m2

def get_related_models(modelnames, stoplist=set(), applabel='amcat'):
    """Get related models

    Finds all models reachable from the given model in the graph of
    (foreign key) relations. If stoplist is given, don't consider edges
    from these nodes.

    @type modelnames: str
    @param modelnames: the name of the model to start from
    @type stoplist: sequence of str
    @param stoplist: models whose children we don't care about
    @return: sequence of model classes
    """
    _models = set([models.get_model(applabel, modelname) for modelname in modelnames])
    stops = set([models.get_model(applabel, stop) for stop in stoplist])
    while True:
        related = set(get_all_related(_models - stops)) # seed from non-stop models
        new = related - _models 
        if not new: return _models
        _models |= new


def get_or_create(model_class, **attributes):
    """Retrieve the instance of model_class identified by the given attributes,
    or if not found, create a new instance with these attributes"""
    try:
        return model_class.objects.get(**attributes)
    except model_class.DoesNotExist:
        return model_class.objects.create(**attributes)


@contextmanager
def list_queries(dest=None, output=False, printtime=False, outputopts={}):
    """Context manager to print django queries

    Any queries that were used in the context are placed in dest,
    which is also yielded.
    Note: this will set settings.DEBUG to True temporarily.
    """
    t = time.time()
    if dest is None: dest = []
    from django.conf import settings
    from django.db import connection
    nqueries = len(connection.queries)
    debug_old_value = settings.DEBUG
    settings.DEBUG = True
    try:
        yield dest
        dest += connection.queries[nqueries:]
    finally:
        settings.DEBUG = debug_old_value
        if output:
            print("Total time: %1.4f" % (time.time() - t))
            query_list_to_table(dest, output=output, **outputopts)


def query_list_to_table(queries, maxqlen=120, output=False, normalise_numbers=True, **outputoptions):
    """Convert a django query list (list of dict with keys time and sql) into a table3
    If output is non-False, output the table with the given options
    Specify print, "print", or a stream for output to be printed immediately
    """
    time = collections.defaultdict(list)
    for q in queries:
        query = q["sql"]
        if normalise_numbers:
            query = re.sub(r"\d+", "#", query)
        #print(query)
        time[query].append(float(q["time"]))
    t =  ObjectTable(rows = time.items())
    t.addColumn(lambda (k, v) : len(v), "N")
    t.addColumn(lambda (k, v) : k[:maxqlen], "Query")
    cum = t.addColumn(lambda (k, v):  "%1.4f" % sum(v), "Cum.")
    t.addColumn(lambda (k, v):  "%1.4f" % (sum(v) / len(v)), "Avg.")
    t = SortedTable(t, sort=cum)
    if output:
        if "stream" not in outputoptions and output is not True:
            if output in (print, "print"):
                import sys
                outputoptions["stream"] = sys.stdout
            else:
                outputoptions["stream"] = output
        t.output(**outputoptions)
    return t

def get_ids(objects):
    """Convert the given object(s) to integers by asking for their .pk.
    Safe to call on integer objects"""
    for obj in objects:
        if not isinstance(obj, int):
            obj = obj.pk
        yield obj

from django.dispatch import Signal
from types import NoneType

def receiver(signal, sender=None, **kwargs):
    """
    A decorator for connecting receivers to signals. Used by passing in the
    signal and keyword arguments to connect::

        @receiver(post_save, sender=MyModel)
        def signal_receiver(sender, **kwargs):
            ...

    """
    def _decorator(func):
        if isinstance(signal, Signal):
            signals = [signal]
        else:
            signals = signal
        if isinstance(sender, (NoneType, type)):
            senders = [sender]
        else:
            senders = sender
        for sig in signals:
            for sen in senders:
                sig.connect(func, sen, **kwargs)
        return func
    return _decorator


class JsonField(models.Field):
    __metaclass__ = models.SubfieldBase
    serialize_to_string = True
    def get_internal_type(self):
        return "TextField"
    def value_to_string(self, obj):
        return self.get_prep_value(self._get_val_from_obj(obj))
    def get_prep_value(self, value):
        if value:
            return json.dumps(value)
        return None
    def to_python(self, value):
        if isinstance(value, (str, unicode)):
            return json.loads(value)
        return value


###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest

class TestDjangoToolkit(amcattest.AmCATTestCase):
    def test_related_models(self):
        """Test get_related_models function. Note: depends on the actual amcat.models"""

        for start, stoplist, result in [
            (('Sentence',), ('Project',), ['Article', 'Language', 'Medium', 'Project', 'Sentence']),
            ]:

            related = get_related_models(start, stoplist)
            related_names = set(r.__name__ for r in related)
            self.assertEqual(related_names, set(result))

    def test_queries(self):
        """Test the list_queries context manager"""
        u = amcattest.create_test_user()
        with list_queries() as l:
            amcattest.create_test_project(owner=u)
        #query_list_to_table(l, output=print)
        self.assertEquals(len(l), 2) # create project, create role for owner

    def test_from_querydict(self):
        di = dict(a=1, b=[2,3])
        self.assertEqual(to_querydict(di), QueryDict("a=1&b=2&b=3"))

    def test_to_querydict(self):
        d = to_querydict(dict(a=1, b=[2,3]))
        self.assertEqual(d.get("a"), "1")
        self.assertEqual(d.get("b"), "3")
        self.assertEqual(d.getlist("a"), ["1"])
        self.assertEqual(d.getlist("b"), ["2","3"])

        self.assertFalse(d._mutable)
        d = to_querydict({}, mutable=False)
        self.assertFalse(d._mutable)
        d = to_querydict({}, mutable=True)
        self.assertTrue(d._mutable)


    def test_get_or_create(self):
        """Test the get or create operation"""
        from amcat.models.medium import Medium
        name = "dsafdsafdsafDSA_amcat_test_medium"
        Medium.objects.filter(name=name).delete()
        self.assertRaises(Medium.DoesNotExist, Medium.objects.get, name=name)
        m = get_or_create(Medium, name=name)
        self.assertEqual(m.name, name)
        m2 = get_or_create(Medium, name=name)
        self.assertEqual(m, m2)

    def test_db_supports_distinct_on(self):
        self.assertTrue(db_supports_distinct_on() in (True, False))
