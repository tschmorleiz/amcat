import threading, subprocess, logging
from amcat.nlp import naf
log = logging.getLogger(__name__)

ALPINO_HOME="/home/wva/Alpino"
PIPE = "{alpino_home}/Tokenization/tok | {alpino_home}/bin/Alpino end_hook=dependencies -parse"

class AlpinoReader(threading.Thread):
    def __init__(self, stream, article):
        threading.Thread.__init__(self)
        self.stream = stream
        self.article = article
        self.current_sentence = None
        self.exception = None
        
    def run(self):
        log.info("Listening for Alpino output..")
        line = None
        try:
            while True:
                line = self.stream.readline()
                if not line: break

                line = line.strip().split("|")
                sid = int(line[-1])
                if self.current_sentence is None or sid != self.current_sentence.sentence_id:
                    self.current_sentence = self.article.create_sentence(sentence_id = sid)
                    self.current_sentence.terms_by_offset = {} 

                interpret_line(self.current_sentence, line)
        except Exception, e:
            log.exception("Error on parsing line {line!r}".format(**locals()))
            self.exception = e

def parse(text):
    cmd = PIPE.format(alpino_home=ALPINO_HOME)
    article = naf.NAF_Article()
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    a = AlpinoReader(p.stdout, article)
    a.start()
    p.stdin.write(text)
    p.stdin.close()
    a.join()
    if a.exception:
        raise a.exception
        
    return article
    
def interpret_line(sentence, line):
    if len(line) != 16:
        raise ValueError("Cannot interpret line %r, has %i parts (needed 16)" % (line, len(line)))
    sid = int(line[-1])
    parent = interpret_token(sentence, *line[:7])
    child = interpret_token(sentence, *line[8:15])
    func, rel = line[7].split("/")
    sentence.add_dependency(child, parent, rel)
    
def interpret_token(sentence, lemma, word, begin, _end, dummypos, dummypos2, pos):
    begin = int(begin)
    term = sentence.terms_by_offset.get(begin)
    if not term:
        if "(" in pos:
            major, minor = pos.split("(", 1)
            minor = minor[:-1]
        else:
            major, minor = pos, None
        if "_" in major:
            m2 = major.split("_")[-1]
        else:
            m2 = major
        cat = POSMAP.get(m2)
        if not cat:
            raise Exception("Unknown POS: %r (%s/%s/%s/%s)" % (m2, major, begin, word, pos))
            
        term = sentence.add_word(begin, word, lemma, pos=cat, term_extra={'major' : major, 'minor' : minor})
        sentence.terms_by_offset[begin] = term
    return term


POSMAP = {"pronoun" : 'O',
          "verb" : 'V',
          "noun" : 'N',
          "preposition" : 'P',
          "determiner" : "D",
          "comparative" : "C",
          "adverb" : "B",
          'adv' : 'B',
          "adjective" : "A",
          "complementizer" : "C",
          "punct" : ".",
          "conj" : "C",
          "tag" : "?",
          "particle": "R",
          "name" : "M",
          "part" : "R",
          "intensifier" : "B",
          "number" : "Q",
          "cat" : "Q",
          "n" : "Q",
          "reflexive":  'O',
          "conjunct" : 'C',
          "pp" : 'P',
          'anders' : '?',
          'etc' : '?',
          'enumeration': '?',
          'np': 'N',
          'p': 'P',
          'quant': 'Q',
          'sg' : '?',
          'zo' : '?',
          'max' : '?',
          'mogelijk' : '?',
          'sbar' : '?',
          '--' : '?',
          }


if __name__ == '__main__':
    import sys    
    a = parse(sys.stdin.read())
    print a.to_json(indent=2)
