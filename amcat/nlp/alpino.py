import threading, subprocess, logging
from amcat.nlp import naf
log = logging.getLogger(__name__)

ALPINO_HOME="/home/wva/Alpino"
ALPINO = ["bin/Alpino","end_hook=dependencies","-parse"]
TOK = ["Tokenization/tok"]

def tokenize(text):
    if isinstance(text, unicode): text=text.encode("utf-8")

    p = subprocess.Popen(TOK, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ALPINO_HOME)
    tokens, err = p.communicate(text)
    tokens = tokens.replace("|", "") # alpino interprets 'sid | line' as sid indicator
    return tokens

def parse(tokens):
    p = subprocess.Popen(ALPINO, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         cwd=ALPINO_HOME, env={'ALPINO_HOME': ALPINO_HOME})
    parse, err = p.communicate(tokens)
    try:
        return interpret_parse(parse)
    except:
        import tempfile
        h, fnt = tempfile.mkstemp()
        open(fnt, 'w').write(tokens)
        h, fnp = tempfile.mkstemp()
        open(fnp, 'w').write(parse)

        log.exception("Error on interpreting parse! Parse written to {fnp}, tokens to {fnt}".format(**locals()))
        raise
    

def interpret_parse(parse):
    article = naf.NAF_Article()
    current_sentence = None

    for line in parse.split("\n"):
        if not line.strip(): continue
        line = line.strip().split("|")
        sid = int(line[-1])
        if current_sentence is None or sid != current_sentence.sentence_id:
            current_sentence = article.create_sentence(sentence_id = sid)
            current_sentence.terms_by_offset = {} 
        interpret_line(current_sentence, line)
        
    return article
    
def interpret_line(sentence, line):
    if len(line) != 16:
        raise ValueError("Cannot interpret line %r, has %i parts (needed 16)" % (line, len(line)))
    sid = int(line[-1])
    parent = interpret_token(sentence, *line[:7])
    child = interpret_token(sentence, *line[8:15])
    func, rel = line[7].split("/")
    sentence.add_dependency(child.term_id, parent.term_id, rel)
    
def interpret_token(sentence, lemma, word, begin, _end, dummypos, dummypos2, pos):
    begin = int(begin)
    term = sentence.terms_by_offset.get(begin)
    if not term:
        if pos == "denk_ik": pos = "verb"
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
    a = naf.NAF_Article()
    
    line="waar|Waar|0|1|adv|adv(er_loc,ywh)|er_wh_loc_adverb|nucl/tag|denk|denk|5|6|verb|verb(denk_ik)|denk_ik|106".split("|")

    for line in sys.stdin:
        print line
        if line.startswith("#"): continue
        s = a.create_sentence()
        s.terms_by_offset={}
        interpret_line(s, line.split("|"))
        
    
    #a = parse(sys.stdin.read())
    #print a.to_json(indent=2)
