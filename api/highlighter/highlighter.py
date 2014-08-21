from django.http import HttpResponse, HttpResponseBadRequest
from amcat.models.coding.codingjob import CodingJob
from amcat.models.article import Article
from django.core.cache import cache
import json
import snowballstemmer
import random
import math

def articleschema(request):
    return highlight(request, 'articleschema')

def unitschema(request):
    return highlight(request, 'unitschema')

def highlight(request, schematype):
    codingjob_id = request.GET.get('codingjob_id')
    article_id = request.GET.get('article_id')

    # check paramaters
    if codingjob_id is None or article_id is None:
        return HttpResponseBadRequest()

    cj = CodingJob.objects.get(pk=codingjob_id)
    article = Article.objects.get(pk=article_id)

    keywords = []

    # create variable keywords list
    if schematype == "articleschema":
        schema = cj.articleschema
    else:
        schema = cj.unitschema
    for csf in schema.fields.all():
        keywords.append(csf.keywords)

    article_matrix = []
    current_parnr = 0;

    # create matrix article sentences
    for sentence in article.sentences.all():
        if sentence.parnr != current_parnr:
            article_matrix.append([])
            current_parnr = sentence.parnr
        article_matrix[-1].append(sentence.sentence)

    # get and respond with highlighting scores
    hash_value = highlighting_hash(article_matrix, keywords)
    result = from_cache(article_id, schema.id, hash_value)
    if result is None:
        ha = HighlighterArticles()
        result = ha.getHighlightingsArticle(article_matrix, keywords, None)
        to_cache(article_id, schema.id, hash_value, result)
    return HttpResponse(json.dumps(result), content_type='application/json')


def highlighting_hash(article_matrix, keywords):
    return hash(str(article_matrix) + ":" + str(keywords))


def from_cache(article_id, schema_id, hash_value):
    article_cache = cache.get("highlighting-{0}".format(article_id))
    if article_cache is None:
        return None
    codingjob_cache = None
    if schema_id in article_cache:
        codingjob_cache = article_cache[schema_id]
    if codingjob_cache is None:
        return None
    if not codingjob_cache['hash'] == hash_value:
        return None
    return codingjob_cache['value']

def to_cache(article_id, schema_id, hash_value, result):
    article_cache = cache.get("highlighting-{0}".format(article_id))
    if article_cache is None:
        article_cache = {}
    article_cache[schema_id] = {}
    article_cache[schema_id]['hash'] = hash_value
    article_cache[schema_id]['value'] = result
    cache.set("highlighting-{0}".format(article_id), article_cache)
    cache.close()


class HighlighterArticles:
# input: 
# article: two-dimensional array of the article: the first dimension corresponds to the paragraph, second corresponds to sentences. 
# variable_keywords: one-dimenstional array of comma-separated keywords
# variable_pages: array of the page numbers assigned to the variables (index identical to variable_keywords).
# output: three-dimensional array: paragraph-sentence-variable, meaning that for every sentence in a paragraph we have scores \in [0,1] giving the highlighting for each variable
	def getHighlightingsArticle(self, article, variable_keywords, variable_pages):
		stemmer = snowballstemmer.stemmer("german")
		word_idx = {}
		word_count = {}
	 	words_used = []
	 	index_used = []
	 	total_words = 0;
		for i in range(0, len(article)):
			for j in range(0, len(article[i])):
				article[i][j] = article[i][j].split(" ");
				for k in range(0, len(article[i][j])):
					# article[i][j][k]=chrtran(article[i][j][k], goodchars, "")
					article[i][j][k]=stemmer.stemWord(article[i][j][k])
					words_used.append(article[i][j][k])
					
		for i in range(0, len(variable_keywords)):
			if ((variable_keywords[i] != None) and (variable_keywords[i]!="")):
				keywords_split = variable_keywords[i].split(",")
				# variable_keywords[i]=chrtran(variable_keywords[i], goodchars, "")
	 			for j in range(0, len(keywords_split)):
						keywords_split[j]=stemmer.stemWord(keywords_split[j])
		 				words_used.append(keywords_split[j])
		 		variable_keywords[i]=keywords_split
		 		
		words_used = set(words_used)		
		
		# get word index
		f = open("/amcat/jgibblda/models/pol/wordmap.txt", "r")
		first = True
		line_counter = 0
		for line in f:	
			if (line_counter == 0):
				total_words = int(line)
			if (line_counter > 0):
				line_split=line.split(" ")
				word = line_split[0]
				count = line_split[1]
				if (word in words_used):
					index_used.append(int(count))
					#word_count[line_counter-1]=count
					word_idx[word]=int(count)
					words_used.remove(word)
			line_counter+=1
		set(index_used)
		
		for i in range(0, len(article)):
			for j in range(0, len(article[i])):
				for k in range(0, len(article[i][j])):
					if (k in range(0, len(article[i][j]))):
						if (article[i][j][k] in words_used):
							del article[i][j][k]
							k-=1
		
		for i in range(0, len(variable_keywords)):
			if ((variable_keywords[i] != None) and (variable_keywords[i]!="")):
	 			for j in range(0, len(variable_keywords[i])):
	 				if (j in range(0, len(variable_keywords[i]))):
						if (variable_keywords[i][j] in words_used):
							del variable_keywords[i][j]
							j -= 1
		# get p(w|z) only for used words in article & keywords
		pwz = {}
		f = open("/amcat/jgibblda/models/pol/model-final.phi", "r")
		# number of topics
		K = 0
		line_counter=0;
		for line in f:
			line_values = line.split(" ");
			word_values = [];
			for j in range(0, len(line_values)):
				#skip words which do not appear in the keywords
				if (j in index_used):
					if (not (j in pwz)):
						pwz[j]=[]
					pwz[j].append(float(line_values[j]))
			K+=1
			
		
		# get p(z|d)
		#  each sentence is stored in article[i][j]
		# double[] pp = new double[K];
		# 		for (int qiter = 0; qiter < niter; qiter++) {
		# 			for (int m = 0; m < nmkq.length; m++) {
		# 				for (int n = 0; n < wq[m].length; n++) {
		# 					// decrement
		# 					int k = zq[m][n];
		# 					int t = wq[m][n];
		# 					nmkq[m][k]--;
		# 					// compute weights
		# 					double psum = 0;
		# 					for (int kk = 0; kk < pp.length; kk++) {
		# 						pp[kk] = (nmkq[m][kk] + alpha) * phi[kk][t];
		# 						psum += pp[kk];
		# 					}
		# 					// sample
		# 					double u = rand.nextDouble() * psum;
		# 					psum = 0;
		# 					int kk = 0;
		# 					for (kk = 0; kk < pp.length; kk++) {
		# 						psum += pp[kk];
		# 						if (u <= psum) {
		# 							break;
		# 						}
		# 					}
		# 					// reassign and increment
		# 					zq[m][n] = kk;
		# 					try {
		# 						nmkq[m][kk]++;
		# 					} catch (Exception e) {	
		# 						System.out.println(Vectors.print(pp));
		# 					}
		# 				} // n
		# 			} // m
		# 		} // i
		qiter = 10
		nmk = [0]*K
		nm = 0
		z = []
		mu = 1
		alpha=K/50.0
		lambda_influence=0.5
		for i in range(0, len(article)):
			zi = []
			for j in range(0, len(article[i])):
				zij = []
				for k in range(0, len(article[i][j])):
					topic_chosen = int(math.floor(random.random()*K))
					zij.append(topic_chosen)
					nmk[topic_chosen] += 1
					nm += 1
					if (k in range(0, len(article[i][j]))):
						if (article[i][j][k] in word_idx):
							article[i][j][k] = word_idx[article[i][j][k]]
						else:
							del article[i][j][k]
							k-=1
				zi.append(zij)
			z.append(zi)
				
		for i in range(0, len(variable_keywords)):
			if ((variable_keywords[i]!=None) and (variable_keywords[i]!="")):
					for j in range(0, len(variable_keywords[i])):			
						variable_keywords[i][j] = word_idx[variable_keywords[i][j]]
		
		for i in range(0, qiter):
			#assign new topics
			#z = [[]] * len(article)
			for i in range(0, len(article)):
				#z[i]=[[]]*len(article[i])
				for j in range(0, len(article[i])):
					for k in range(0, len(article[i][j])):
						nmk[z[i][j][k]]-=1
						nm-=1
						psum=0
						pword=[0]*K
						for topic in range(0,K):
							pword[topic] = pwz[article[i][j][k]][topic]
							pword[topic]*= (nmk[topic]+alpha)/(nm+K*alpha)
							psum+=pword[topic]
						for topic in range(0,K):
							pword[topic]/=psum
							if(topic>0):
								pword[topic]+=pword[topic-1]
											
						random_p=random.random()
						z[i][j][k]=0
						for topic in range(0,K):
							if random_p < pword[topic]:
								z[i][j][k]=topic
								break
						nmk[z[i][j][k]]+=1
						nm+=1
			
		highlight = [[]]*len(article)
		sum_p_keywords = [0]*len(variable_keywords)
		max_p_keywords = 0;
		for i in range(0, len(article)):
			highlight[i] = [[0]]*len(article[i])
			for j in range(0, len(article[i])):
				ptopic_sentence=[0]*K
				keyword_found = [0]*len(variable_keywords)
				for k in range(0, len(article[i][j])):
					for p in range(0, len(variable_keywords)):
						if (article[i][j][k] in variable_keywords[p]):
							keyword_found[p]+=1
					psum=0
					ptopic=[0]*K
					for topic in range(0,K):
						ptopic[topic]=pwz[article[i][j][k]][topic]*(nmk[topic]+alpha)/(nm+K*alpha)
						psum+=ptopic[topic]
					for topic in range(0,K):
						ptopic[topic]/=psum
						ptopic_sentence[topic]+=ptopic[topic]
				for topic in range(0,K):
					ptopic_sentence[topic]/=K
				p_keywords = [0]*len(variable_keywords)
				for p in range(0, len(variable_keywords)):
					if ((variable_keywords[p]!=None) and (variable_keywords[p]!="")):
						for q in range(0, len(variable_keywords[p])):
							for topic in range(0,K):
								p_keywords[p]+= lambda_influence * pwz[variable_keywords[p][q]][topic] * ptopic_sentence[topic]
						p_keywords[p] *= (lambda_influence / len(variable_keywords[p]))
						#p_keywords[p]+= (1-lambda_influence) * (1-(len(article[i]) / (len(article[i]) + mu)) * (word_count[variable_keywords[p][q]]/total_words)
						#(len(article[i]) / (len(article[i]) + mu)) 
						p_keywords[p]+= (1-lambda_influence) * keyword_found[p] / len(article[i][j])
						print keyword_found
					sum_p_keywords[p] += p_keywords[p]
					max_p_keywords = max(max_p_keywords,p_keywords[p])
				highlight[i][j]=p_keywords
				
		for i in range(0, len(article)):
			for j in range(0, len(article[i])):
				for p in range(0, len(variable_keywords)):
					#highlight[i][j][p]/=sum_p_keywords[p]
					highlight[i][j][p]/=max_p_keywords
		return highlight
	pass	


#article=[["eins zwei"],["drei vier funf","sechs sieben acht"]]
#variable_keywords = ["test,bla,eins","test,vier,eins","vier,acht,bla"]
#highlighter = HighlighterArticles()
#variable_pages = []
#highlighting = highlighter.getHighlightingsArticle(article,variable_keywords,variable_pages)
#print(highlighting)
