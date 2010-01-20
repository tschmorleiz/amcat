from itertools import izip, count
import sbd, re, dbtoolkit


def splitArticle(art):
    if art.sentences: return
    text = art.text
    if not text:
        toolkit.warn("Article %s empty, adding headline only" % art.id)
        text = ""                                                                                                             
    text = re.sub(r"q11\s*\n", "\n\n",text)                                                                                   
    #if article.byline: text = article.byline + "\n\n" + text                                                                 
    if art.headline: text = art.headline.replace(";",".")+ "\n\n" + text                                              
    spl = sbd.splitPars(text)                                                                                                 
    for parnr, par in izip(count(1), spl):                                                                                    
        for sentnr, sent in izip(count(1), par):                                                                              
            sent = sent.strip()                                                                                               
            orig = sent                                                                                                       
            [sent], encoding = dbtoolkit.encodeTexts([sent])                                                                  
            if len(sent) > 6000:
                raise Exception("Sentence longer than 6000 characters, this is not normal!")
            art.db.insert("sentences", {"articleid":art.id, "parnr" : parnr, "sentnr" : sentnr, "sentence" : sent, 'encoding': encoding})
    art.removeCached("sentences")
    
def splitArticles(articles):                                                                                            
    error = ''
    for article in articles:
        try:
            splitArticle(article)
            article.db.commit()
        except Exception, e:
            error += '%s: %s\n' % (article.id , e)    
    return error or None

if __name__ == '__main__':
    import dbtoolkit, article
    a = article.Article(dbtoolkit.amcatDB(), 44532714)
    print a.sentences
    print splitArticles([a])
    print a.sentences