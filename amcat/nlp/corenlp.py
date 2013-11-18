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
# Based on (but mostly rewritten) 
#    https://github.com/dasmith/stanford-corenlp-python (GPL)

"""
Python interface for the Stanford CoreNLP suite.
"""

import os, sys, time
import re
import logging
import pexpect
from cStringIO import StringIO
from .naf import NAF_Article, Coreference_target
log = logging.getLogger(__name__)

def parse_results(lines):
    """ This is the nasty bit of code to interact with the command-line
    interface of the CoreNLP tools.  Takes a string of the parser results
    and then returns a Python list of dictionaries, one for each parsed
    sentence.
    """
    
    lines = iter(lines)
    lines.next() # skip first line (echo of sentence)

    article = NAF_Article()
    parse_sentences(article, lines)
    parse_coreferences(article, lines)
    return article

def parse_sentences(article, lines):
    while True:
        try:
            parse_sentence(article, lines)
        except StopIteration:
            break

def parse_sentence(article, lines):
    """
    Parse a sentence from the lines iterator, consuming lines in the process
    Raises StopIteration if the end of the sentences is reached (explicitly or from lines.next())
    """
    nr = get_sentence_no(lines)
    text = lines.next()
    log.debug("Parsing sentence {nr}: {text!r}".format(**locals()))
    sentence = article.create_sentence()
    # split words line into minimal bracketed chunks and parse those
    for s in re.findall('\[([^\]]+)\]', lines.next()):
        wd = dict(parse_word(s))
        entity = wd.get("NamedEntityTag", None)
        sentence.add_word(wd["CharacterOffsetBegin"], wd["Text"], wd["Lemma"], wd["PartOfSpeech"],
                          entity_type=(None if entity == "O" else entity))
    parsetree = " ".join(p.strip() for p in parse_tree(lines))
    tuples = parse_tuples(sentence, lines)
    return sentence


def get_sentence_no(lines):
    """Return the sentence number, or raise StopIteration if EOF or Coreference Set is reached"""
    line = lines.next()
    while not line.strip(): line = lines.next() # skip leading blanks
    if line == "Coreference set:":
        raise StopIteration 
    m = re.match("Sentence #\s*(\d+)\s+", line)
    if not m: raise Exception("Cannot interpret 'sentence' line {line!r}".format(**locals()))
    return int(m.group(1))

def parse_tree(lines):
    for line in lines:
        if not line.strip():
            break
        yield line

def parse_tuples(sentence, lines):
    for line in lines:
        if not line.strip():
            return
        m = re.match(r"(\w+)\(.+-([0-9']+), .+-([0-9']+)\)", line)
        if not m:
            raise Exception("Cannot interpret 'tuples' line: {line!r}".format(**locals()))
        rfunc, from_index, to_index = m.groups()
        from_term = sentence.terms[int(from_index)].term_id
        to_term = sentence.terms[int(to_index)].term_id
        sentence.add_dependency(from_term, to_term, rfunc)

def parse_word(s):
  '''Parse word features [abc=... def = ...]
  Also manages to parse out features that have XML within them
  @return: an iterator of key, value pairs
  '''
  result = {}
  # Substitute XML tags, to replace them later
  temp = {}
  for i, tag in enumerate(re.findall(r"(<[^<>]+>.*<\/[^<>]+>)", s)):
    temp["^^^%d^^^" % i] = tag
    s = s.replace(tag, "^^^%d^^^" % i)
  for attr, val in re.findall(r"([^=\s]*)=([^=\s]*)", s):
    if val in temp:
      val = temp[val]
    else:
        yield attr, val

def parse_coref_group(s):
    s = s.replace("[", "")
    s = s.replace(")", "")
    return map(int, s.split(","))

def parse_coreferences(article, lines):
    while True:
        #TODO: what do multiple coref lines in one set mean?
        corefs = list(parse_coreference(lines))
        if not corefs:
            break
        for coref in corefs:
            co = article.create_coreference()
            for sent_index, head_index, from_index, to_index in coref:
                s = article.sentences[sent_index - 1]
                head = s.terms[head_index - 1]
                terms = s.terms[from_index - 1 : to_index - 1]
                co.spans.append([Coreference_target(term.term_id, term == head)
                                 for term in terms])

def parse_coreference(lines):
    for line in lines:
        if line == "Coreference set:":
            return
        if not line.strip():
            continue
        m = re.match(r'\s*\((\S+)\) -> \((\S+)\), that is: \".*\" -> \".*\"', line)
        if not m:
            raise Exception("Coref sets not found in line {line!r}".format(**locals()))
        yield map(parse_coref_group, m.groups())


class StanfordCoreNLP(object):
    """ 
    Command-line interaction with Stanford's CoreNLP java utilities.

    Can be run as a JSON-RPC server or imported as a module.
    """
    
    def __init__(self, timeout=600, **classpath_args):
        """
        Start the CoreNLP server as a java process. Arguments are used to locate the correct jar files.

        @param corenlp_path: the directory containing the jar files
        @param corenlp_version: the yyyy-mm-dd version listed in the jar name
        @param models_version: if different from the main version, the version date of the models jar
        @param timeout: Time to wait for a parse before giving up
        """

        self.timeout = timeout
        cmd = self.get_command(classname = "edu.stanford.nlp.pipeline.StanfordCoreNLP",
                               **classpath_args)

        log.info("Starting the Stanford Core NLP parser.")
        log.debug("Command: {cmd}".format(**locals()))
        self._corenlp_process = pexpect.spawn(cmd)
        self._wait_for_corenlp_init()

    def _get_classpath(self, corenlp_path, corenlp_version, models_version=None):
        """
        Construct the classpath from jar names, base path, and version number.
        Raises an Exception if any of the jars cannot be found
        """


    def _wait_for_corenlp_init(self):
        """Give some progress feedback while waiting for server to initialize"""
        for module in ["Pos tagger", "NER-all", "NER-muc", "ConLL", "PCFG"]:
            log.debug("Loading {module}".format(**locals()))
            i = self._corenlp_process.expect(["done.", "Exception"], timeout=600)
            if i == 1:
                log.warn(self._corenlp_process.read())
                raise Exception("Exception from CoreNLP")
        log.debug(" ..  Finished loading modules...")
        self._corenlp_process.expect("Entering interactive shell.")
        log.info("NLP tools loaded.")


    def _get_results(self):
        """
        Get the raw results from the corenlp process
        """
        copy = open("/tmp/parse_log", "w")
        buff = StringIO()
        while True: 
            try:
                incoming = self._corenlp_process.read_nonblocking (2000, 1)
            except pexpect.TIMEOUT:
                log.debug("Waiting for CoreNLP process; buffer: {!r} ".format(buff.getvalue()))
                continue
            # original broke out of loop on EOF, but EOF is unexpected so rather raise exception
                
            for ch in incoming:
                copy.write(ch)
                if ch == "\n": # return a found line
                    yield buff.getvalue()
                    buff.seek(0)
                    buff.truncate()
                elif ch not in "\r\x07":
                    buff.write(ch)
                    if ch == ">" and buff.getvalue().startswith("NLP>"):
                        return

    def _parse(self, text):
        """
        Call the server and parse the results.
        @return: (sentences, coref)
        """
        # clean up anything leftover, ie wait until server says nothing in 0.3 seconds
        while True:
            try:
                ch = self._corenlp_process.read_nonblocking(4000, 0.3)
            except pexpect.TIMEOUT:
                break

        self._corenlp_process.sendline(text)

        return parse_results(self._get_results())

    def parse(self, text):
        """ 
        This function parses a text string, sends it to the Stanford parser,
        @return: (sentences, coref)
        """
        log.info("Request: {text}".format(**locals()))
        results = self._parse(text)
        print("===", results)
        log.info("Result: {results}".format(**locals()))
        return results



def get_classpath(corenlp_path=None, corenlp_version=None, models_version=None):
    if corenlp_path is None: corenlp_path = os.environ["CORENLP_HOME"]
    if corenlp_version is None: corenlp_version = os.environ.get("CORENLP_VERSION", "3.2.0")
    if models_version is None: models_version = corenlp_version

    jars = ["stanford-corenlp-{corenlp_version}.jar".format(**locals()),
            "stanford-corenlp-{models_version}-models.jar".format(**locals()),
            "joda-time.jar", "xom.jar", "jollyday.jar"]
    jars = [os.path.join(corenlp_path, jar) for jar in jars]
    
    # check whether jars exist
    for jar in jars:
        if not os.path.exists(jar):
            raise Exception("Error! Cannot locate {jar}".format(**locals()))
            
    return ":".join(jars)

    @classmethod
    def get_command(cls, classname, argstr="",memory=None, **classpath_args):
        classpath = get_classpath(**classpath_args)
        memory = "" if memory is None else "-Xmx{memory}".format(**locals())
        if isinstance(argstr, list):
            argstr = " ".join(map(str, argstr))
        return "java {memory} -cp {classpath} {classname} {argstr}".format(**locals())

    @classmethod
    def parse_text(cls, text, **kargs):
        nlp = StanfordCoreNLP(**kargs)
        return nlp.parse(text)

if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.DEBUG)
    parse = parse_text(sys.argv[1])
    print(json.dumps(parse))
    

###########################################################################
#                          U N I T   T E S T S                            #
###########################################################################

from amcat.tools import amcattest

class TestCoreNLP(amcattest.PolicyTestCase):
    def test_interpret(self):
        #TODO Test instead of print :-)
        import amcat
        fn = os.path.join(os.path.dirname(amcat.__file__), "tests", "testfile_corenlp.txt")
        raw_result = open(fn).read()
        lines = [line.strip() for line in raw_result.split("\n")]
        r = parse_results(lines)
        from lxml import etree
        xml = r.generate_xml()
        print etree.tostring(xml, pretty_print=True)
