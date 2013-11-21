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

from __future__ import unicode_literals, print_function, absolute_import

"""
AmCAT - xtas integration

Use process_document[_sync] to process a document with xtas.
This assumes that xtas is running and listening to the same broker and result
backend as amcat. The easiest way to do this is to set amqp as the celery result
backend (so rabbit is both broker and result backend) and to make sure both
amcat and xtas use the same rabbitmq server. 
(add CELERY_RESULT_BACKEND = 'amqp' to settings.py)
"""

from hashlib import md5
from celery.task import Task
from celery.execute import send_task
import time
import celery
import itertools

import logging
log = logging.getLogger(__name__)

KEY = u"paul" # dit kan niet goed zijn :)
TASK_PROCESS_NAME = "process_document"
TASK_PROCESS_FULL = "processing.tasks." + TASK_PROCESS_NAME
TASK_CLEAR = "processing.tasks.clear_cache"
STATE_SENT = 'SENT'

class TaskPending(Exception):
    pass

def _hashid(task, *arg, **args):
    # see xtas.processing.tasks.hashid
    n = '%s(%s,%s)' % (task, repr(arg), repr(args))
    result = md5(n).hexdigest()
    return result

def _get_args(article, *methods):
    document = None
    language = None
    dOptions = {}
    methodlist = [tuple(unicode(x) for x in method)
                  for method in methods]
    aid = article if isinstance(article, int) else article.id
    return [KEY, unicode(aid), document, language, methodlist, dOptions] 

def process_document_sync(article, *methods, **options):
    """
    Ask xtas to process the article, see process_document
    Will halt (wait) until the document is done
    """
    for i in itertools.count():
        try:
            return process_document(article, *methods, **options)
        except TaskPending:
            options.pop('force_resend', None)
            if i < 5:
                time.sleep(.1)
            else:
                time.sleep(1)

def clear_cache(*articles):
    article_ids = [str(a) if isinstance(a, int) else str(a.id)
                   for a in articles]
    t = send_task(TASK_CLEAR, args=(KEY, article_ids))
    t.get()
            
def process_document(article, *methods, **options):
    """
    Ask xtas to process the article with the methodlist.
    The method will raise TaskPending if the task is waiting for completion

    (This is an asynchronous operation, so keeping calling until it is done)
    
    @param methods: one or more (method, args) pairs
    @return: The result if the task is done
    """
    force_resend = options.pop('force_resend', False)
    if options: raise ValueError("Unknwown options: {options}".format(**locals()))
    
    args = _get_args(article, *methods)
    tid = _hashid(TASK_PROCESS_NAME, *args)
    if force_resend:
        state = celery.states.PENDING
    else:
        # check if task already exists
        t = Task.AsyncResult(tid)
        state = t.state
    log.info("Task {tid}: {state}".format(**locals()))
        
    if state == celery.states.SUCCESS:
        return t.get()
    elif state == celery.states.FAILURE:
        raise t.result
    elif state == celery.states.PENDING:
        # PENDING really means UNKNOWN, here meaning UNSENT
        # so, send new task and set state to 'SENT' in task backend
        # (inspired by http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists)
        t = send_task(TASK_PROCESS_FULL, args=args, task_id=tid, kwargs={'hid' : tid})
        t.backend.store_result(tid, None, STATE_SENT)
        raise TaskPending()
    elif state == STATE_SENT:
        raise TaskPending()
        
    raise Exception("No action defined for state {state}".format(**locals()))
    
###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest
import collections

class TestXtas(amcattest.PolicyTestCase):

    #TODO: not very meaningful unit tests since it is hard to test async, but see
    #      http://docs.celeryproject.org/en/latest/django/unit-testing.html
    #      for some ideas...
    
    def test_hash(self):
        method = ('pos', 'stanford')
        
        # task_name = "process_document((u'paul', u'16514', None, None, [(u'pos', u'stanford')], {}),{})"
        # expected_hash = md5(task_name).hexdigest
        expected_hash = '38a3789f1156030f70d222a5d86c5f4c' # from xtas log, but corresponds to line above
        
        self.assertEqual(_hashid(TASK_PROCESS_NAME, *_get_args(16514, method)), expected_hash)
        
