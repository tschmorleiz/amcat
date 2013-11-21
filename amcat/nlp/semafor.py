from __future__ import absolute_import

import socket
import json
from cStringIO import StringIO

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

def get_frames(conll_str):
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

