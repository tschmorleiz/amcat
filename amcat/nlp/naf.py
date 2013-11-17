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
Classes that represent NAF primitives as a named tuple with a final 'extra' argument
"""

from collections import namedtuple
import json


class NAF_Object(object):
    def __new__(self, *args, **kargs):
        if "extra" not in kargs:
            kargs["extra"] = {}
        for k in list(kargs):
            if k not in self._fields:
                kargs["extra"][k] = kargs.pop(k)
        return super(NAF_Object, self).__new__(self, *args, **kargs)
    def __getattr__(self, attr):
        try:
            return self.extra[attr]
        except KeyError:
            raise AttributeError(attr)

class WordForm(NAF_Object, namedtuple("WordForm_base", ["word_id", "sentence_id", "offset", "word", "extra"])):
    pass


###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest

class TestNAF(amcattest.PolicyTestCase):
    def test_wordform(self):
        w = WordForm(1,2,3,"test")
        self.assertEqual(w.word, "test")
        self.assertFalse(w.extra)
        self.assertRaises(AttributeError, getattr, w, "test")
        self.assertEqual(json.dumps(w), '[1, 2, 3, "test", {}]')

        w = WordForm(1,2,3,word="test", test1=1, test2="bla")
        self.assertEqual(w.word, "test")
        self.assertEqual(w.test1, 1)
        self.assertEqual(w.test2, "bla")
        self.assertEqual(json.dumps(w), '[1, 2, 3, "test", {"test1": 1, "test2": "bla"}]')
