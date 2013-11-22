from __future__ import absolute_import

import socket
import json
from cStringIO import StringIO

from . import corenlp

def nc(host, port, input):
    """'netcat' implementation, see http://stackoverflow.com/a/1909355"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect( (host, port ))
    s.sendall(input)
    s.shutdown(socket.SHUT_WR)
    result = StringIO()
    while 1:
        data = s.recv(1024)
        if data == "":
            s.close()
            return result.getvalue()
        result.write(data)

def call_semafor(conll_str):
    """
    Use semafor to parse the conll_str. Assumes that semafor is running as a web service on
    localhost:9888, and assumes conll_str to be a string representation of parse trees in conll format
    """
    result = nc("localhost", 9888, conll_str)
    try:
        open("/tmp/semafor.txt", "w").write(result)
    except:
        pass
    
    return [json.loads(sent) for sent in result.split("\n") if sent.strip()]

def get_frames(naf_article):
    for sid in naf_article.sentence_ids:
        for frame in get_sentence_frames(naf_article, sid):
            yield frame

def get_sentence_frames(naf_article, sid):
    words = [w for w in naf_article.words if w.sentence_id == sid]
    conll = corenlp.to_conll(naf_article, sid)
    sent, = call_semafor(conll)
    frames, tokens = sent["frames"], sent["tokens"]
    assert len(tokens) == len(words)

    def get_words(f):
        for span in f["spans"]:
            for i in range(span["start"], span["end"]):
                yield words[i].word_id

    for frame in frames:
        f = {"sentence_id" : sid, "name" : frame["target"]["name"], "target" : list(get_words(frame["target"])), "elements" : []}
        for a in frame["annotationSets"][0]["frameElements"]:
            f["elements"].append({"name" : a["name"], "target" : list(get_words(a))})
        yield f
    
