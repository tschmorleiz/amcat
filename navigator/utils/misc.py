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
import os
import random
import string
import types
from hashlib import sha1
import logging;

from django.core.cache import cache

log = logging.getLogger(__name__)

def gen_random(n=8):
    return ''.join(random.choice(string.ascii_uppercase) for x in range(n))

class UUIDLogMiddleware(object):
    def process_request(self, request):
        request.uuid = gen_random(10)
        ppid, pid = os.getppid(), os.getpid()
        url = "?".join((request.META["PATH_INFO"], request.META["QUERY_STRING"]))
        log.info("Start of request {request.uuid} ({ppid}, {pid}): {url}".format(**locals()), extra={"request":request})

    def process_response(self, request, response):
        if hasattr(request, "uuid"):
            log.info("End of request {}".format(request.uuid))
        return response

def session_pop(session, key, default=None):
    """
    Pops a key from a session object, but does not raise a KeyError when
    the key is not found.

    @type session: django.backends.base.SessionBase
    @type key: basestr
    """
    try:
        return session.pop(key)
    except KeyError:
        return default

def cache_function(length):
    """
    Caches a function, using the function itself as the key, and the return
    value as the value saved. It passes all arguments on to the function, as
    it should.
    
    @type length: integer
    @param length: seconds to cache
    """
    def decorator(func):
        def inner_func(*args, **kwargs):
            keys = map(str, (func.__module__, func.__name__, args, kwargs))
            key = sha1("_".join(keys)).hexdigest()

            if cache.has_key(key):
                return cache.get(key)
            else:
                result = func(*args, **kwargs)

                if type(result) == types.GeneratorType:
                    result = tuple(result)

                cache.set(key, result, length)
                return result
        return inner_func
    return decorator
