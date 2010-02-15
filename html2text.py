"""html2text: Turn HTML into equivalent Markdown-structured text."""
__version__ = "2.0, alpha"
__author__ = "Aaron Swartz (me@aaronsw.com)"
__copyright__ = "(C) 2004 Aaron Swartz. GNU GPL 2."

# TODO: Word wrap.

import re, sys, urllib, htmlentitydefs
import sgmllib
sgmllib.charref = re.compile('&#([xX]?[0-9a-fA-F]+)[^0-9a-fA-F]')

# Use Unicode characters instead of their ascii psuedo-replacements
UNICODE_SNOB = 0

# Put the links after each paragraph instead of at the end.
LINKS_EACH_PARAGRAPH = 0

### Entity Nonsense ###

def name2cp(k):
	if k == 'apos': return ord("'")
	if hasattr(htmlentitydefs, "name2codepoint"): # requires Python 2.3
		return htmlentitydefs.name2codepoint[k]
	else:
		k = htmlentitydefs.entitydefs[k]
		if k.startswith("&#") and k.endswith(";"): return int(k[2:-1]) # not in latin-1
		return ord(k.decode('ISO-8859-1'))

unifiable = {'rsquo':"'", 'lsquo':"'", 'rdquo':'"', 'ldquo':'"', 
'copy':'(C)', 'mdash':'--', 'nbsp':' ', 'rarr':'->', 'larr':'<-', 'middot':'*',
'oelig':'oe', 'aelig':'ae', 
'agrave':'a', 'aacute':'a', 'acirc':'a', 'atilde':'a', 'auml':'a', 'aring':'a', 
'egrave':'e', 'eacute':'e', 'ecirc':'e', 'euml':'e', 
'igrave':'i', 'iacute':'i', 'icirc':'i', 'iuml':'i',
'ograve':'o', 'oacute':'o', 'ocirc':'o', 'otilde':'o', 'ouml':'o', 
'ugrave':'u', 'uacute':'u', 'ucirc':'u', 'uuml':'u'}

unifiable_n = {}

for k in unifiable.keys():
	unifiable_n[name2cp(k)] = unifiable[k]

def charref(name):
	if name[0] in ['x','X']:
		c = int(name[1:], 16)
	else:
		c = int(name)
	
	if not UNICODE_SNOB and c in unifiable_n.keys():
		return unifiable_n[c]
	else:
		return unichr(c).encode('utf8')

def entityref(c):
	if not UNICODE_SNOB and c in unifiable.keys():
		return unifiable[c]
	else:
		try: name2cp(c)
		except KeyError: return "&" + c
		else: return unichr(name2cp(c)).encode('utf8')

def replaceEntities(s):
	s = s.group(0)
	if s[0] == "#": return charref(s[1:])
	else: return entityref(s)

r_unescape = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));")
def unescape(s):
	return r_unescape.sub(replaceEntities, s)
	
def fixattrs(attrs):
	# Fix bug in sgmllib.py
	if not attrs: return attrs
	newattrs = []
	for attr in attrs:
		newattrs.append((attr[0], unescape(attr[1])))
	return newattrs

### End Entity Nonsense ###

def out(text): sys.stdout.write(text)

def hn(tag):
	if tag[0] == 'h' and len(tag) == 2:
		try:
			n = int(tag[1])
			if n in range(1, 10): return n
		except ValueError: return False

class _html2text(sgmllib.SGMLParser):
	def __init__(self):
		sgmllib.SGMLParser.__init__(self)
		
		self.quiet = 0
		self.p_p = 0
		self.outcount = 0
		self.start = 1
		self.space = 0
		self.a = []
		self.astack = []
		self.acount = 0
		self.list = []
		self.blockquote = 0
		self.pre = 0
		self.startpre = 0
		self.lastWasNL = 0
	
	def close(self):
		sgmllib.SGMLParser.close(self)
		
		self.pbr()
		self.o('', 0, 'end')
		
	def handle_charref(self, c):
		self.o(charref(c))

	def handle_entityref(self, c):
		self.o(entityref(c))
			
	def unknown_starttag(self, tag, attrs):
		self.handle_tag(tag, attrs, 1)
	
	def unknown_endtag(self, tag):
		self.handle_tag(tag, None, 0)

	def handle_tag(self, tag, attrs, start):
		attrs = fixattrs(attrs)
	
		if hn(tag):
			self.p()
			if start: self.o(hn(tag)*"#" + ' ')

		if tag in ['p', 'div']: self.p()
		
		if tag == "br" and start: self.o("  \n")

		if tag in ["head", "style", 'script']: 
			if start: self.quiet += 1
			else: self.quiet -= 1
		
		if tag == "blockquote":
			if start: 
				self.p(); self.o('> ', 0, 1); self.start = 1
				self.blockquote += 1
			else:
				self.blockquote -= 1
				self.p()
		
		if tag in ['em', 'i', 'u']: self.o("_")
		if tag in ['strong', 'b']: self.o("**")
		if tag == "code" and not self.pre: self.o('`') #TODO: `` `this` ``
		
		if tag == "a":
			if start:
				attrs = dict(attrs)
				if attrs.has_key('href'): 
					self.astack.append(attrs)
					self.o("[")
				else:
					self.astack.append(None)
			else:
				if self.astack:
					a = self.astack.pop()
					if a:
						self.acount += 1
						a['count'] = self.acount
						a['outcount'] = self.outcount
						self.o("][" + `a['count']` + "]")
						self.a.append(a)
		
		if tag == "img" and start:
			self.acount += 1
			attrs = dict(attrs)
			if attrs.has_key('src'):
				attrs['href'] = attrs['src']
				attrs['count'] = self.acount
				attrs['outcount'] = self.outcount
				self.a.append(attrs)
				self.o("![")
				if attrs.has_key('alt'): self.o(attrs['alt'])
				self.o("]["+`self.acount`+"]")
		
		if tag in ["ol", "ul"]:
			if start:
				self.list.append({'name':tag, 'num':0})
			else:
				self.list.pop()
			
			self.p()
		
		if tag == 'li':
			if start:
				self.pbr()
				if self.list: li = self.list[-1]
				else: li = {'name':'ul', 'num':0}
				self.o("  "*len(self.list)) #TODO: line up <ol><li>s > 9 correctly.
				if li['name'] == "ul": self.o("* ")
				elif li['name'] == "ol":
					li['num'] += 1
					self.o(`li['num']`+". ")
				self.start = 1
			else:
				self.pbr()
		
		if tag in ['tr']: self.pbr()
		
		if tag == "pre":
			if start:
				self.startpre = 1
				self.pre = 1
			else:
				self.pre = 0
			self.p()
			
	def pbr(self):
		if self.p_p == 0: self.p_p = 1

	def p(self): self.p_p = 2
	
	
	def o(self, data, puredata=0, force=0):
		if not self.quiet: 
			if puredata and not self.pre:
				data = re.sub('\s+', ' ', data)
				if data and data[0] == ' ':
					self.space = 1
					data = data[1:]
			if not data and not force: return
			
			if self.startpre:
				out(" :") #TODO: not output when already one there
				self.startpre = 0
			
			bq = (">" * self.blockquote)
			if not (force and data and data[0] == ">"): bq += (" "*bool(self.blockquote))
			
			if self.pre:
				bq += "    "
				data = data.replace("\n", "\n"+bq)
			
			if self.start:
				self.space = 0
				self.p_p = 0
				self.start = 0

			if force == 'end':
				# It's the end.
				self.p_p = 0
				out("\n")
				self.space = 0


			if self.p_p:
				out(('\n'+bq)*self.p_p)
				self.space = 0
				
			if self.space:
				if not self.lastWasNL: out(' ')
				self.space = 0

			if self.a and ((self.p_p == 2 and LINKS_EACH_PARAGRAPH) or force == "end"):
				if force == "end": out("\n")

				newa = []
				for link in self.a:
					if self.outcount > link['outcount']:
						out("    ["+`link['count']`+"]: " + link['href']) #TODO: base href
						if link.has_key('title'): out(" ("+link['title']+")")
						out("\n")
					else:
						newa.append(link)

				if self.a != newa: out("\n") # Don't need an extra line when nothing was done.

				self.a = newa

			self.p_p = 0
			out(data)
			self.lastWasNL = data and data[-1] == '\n'
			self.outcount += 1

	def handle_data(self, data):
		self.o(data, 1)
	
	def unknown_decl(self, data): pass
		
def html2text(html):
	h = _html2text()
	h.feed(html)
	h.feed("")
	h.close()

if __name__ == "__main__":
	if sys.argv[1:]:
		arg = sys.argv[1]
		if arg.startswith('http://'):
			data = urllib.urlopen(arg).read()
		else:
			data = open(arg, 'r').read()
	else:
		data = sys.stdin.read()
	html2text(data)