# vim:noexpandtab
"""

Google Voice Notify, v0.1
by Mike Krieger <mikekrieger@gmail.com>
edited by Sean Schulte <sirsean@gmail.com>

"""

from cookielib import CookieJar
import simplejson
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
import urllib2
import cPickle as pickle

class GoogleVoiceNotify(object):
	def __init__(self, username, password, listeners=None, picklefile='/tmp/gv_read_messages_picklefile'):
		"""
		Initialize the Google Voice Notifier 
		"""
		# GV username and pass
		self.username = username
		self.password = password
		self.picklefile = picklefile
		self.headers = [("Content-type", "application/x-www-form-urlencoded"),
														('User-Agent', 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'),
														("Accept", "application/xml")]
		# only fetch cookies once
		self.cookies = CookieJar()
		# if a previous session quit but saved state, load it to
		# avoid double notifications
		try:
			cached_fl = open(picklefile, 'r')
			self.read_sms_messages = pickle.load(cached_fl)
			cached_fl.close()
		except Exception, e:
			from collections import defaultdict
			self.read_sms_messages = defaultdict(set)
		"""
			Register a list of listeners that print out notifications.
			Listeners must implement an 'on_notification' method,
			of the format on_notification(event, from_name, message)
		"""
		if type(listeners) in (tuple, list):
			self.listeners = listeners
		elif listeners != None:
			self.listeners = (listeners,)
		else:
			self.listeners = None

	def do_req(self, url, post_data=None):
		# reference: http://media.juiceanalytics.com/downloads/pyGAPI.py
		req = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookies))
		if post_data is not None:
			req.add_data(post_data)
		req.addheaders = self.headers
		f = req.open(url)
		return f

	def get_inbox(self):
		# if we haven't acquired cookies yet
		if len(self.cookies) == 0:
			 # first do the login POST
			login = self.do_req('https://www.google.com/accounts/ServiceLoginBoxAuth?Email=%s&Passwd=%s&service=grandcentral' % (self.username, self.password)).read()
			 # second step is to pass the cookie check
			cookie_check = self.do_req('https://www.google.com/accounts/CheckCookie?chtml=LoginDoneHtml').read()
		sms = self.do_req('https://www.google.com/voice/inbox/recent/sms/').read()
		sp = BeautifulStoneSoup(sms)
		return str(sp.response.html.contents[0])

	def parse_result(self, result):
		sp = BeautifulSoup(result)

		messages = sp.findAll('div', attrs={'class':'gc-message-sms-row'})
		for message in messages:
			from_name = message.findAll('span', attrs={'class':'gc-message-sms-from'})[0].string.strip()[:-1]
			text = message.findAll('span', attrs={'class':'gc-message-sms-text'})[0].string.strip()
			time = message.findAll('span', attrs={'class':'gc-message-sms-time'})[0].string.strip()

			key = self.generate_sms_key(from_name, text, time)

			if not key in self.read_sms_messages:
				self.read_sms_messages[key] = True
				if from_name != 'Me':
					if self.listeners and len(self.listeners) > 0:
						for listener in self.listeners:
							listener.on_notification('SMS', from_name, text)

	def get_voicemails(self):
		# if we haven't acquired cookies yet
		if len(self.cookies) == 0:
			 # first do the login POST
			login = self.do_req('https://www.google.com/accounts/ServiceLoginBoxAuth?Email=%s&Passwd=%s&service=grandcentral' % (self.username, self.password)).read()
			 # second step is to pass the cookie check
			cookie_check = self.do_req('https://www.google.com/accounts/CheckCookie?chtml=LoginDoneHtml').read()
		html = self.do_req('https://www.google.com/voice/inbox/recent/voicemail/').read()
		sp = BeautifulStoneSoup(html)
		return str(sp.response.html.contents[0])
	def parse_voicemails(self, result):
		cleaned = result.replace('</div></div></div></div></div>', '</div></div></div></div>')
		sp = BeautifulSoup(cleaned)
		voicemails = sp.findAll('div', attrs={'class':'goog-flat-button gc-message gc-message-unread'})
		for voicemail in voicemails:
			id = voicemail['id']
			# find all voicemail rows
			rows = voicemail.findAll('table', attrs={'class':'gc-message-tbl'})
			for message in rows:
				from_name = message.findAll('a', attrs={'class':'gc-under gc-message-name-link'})[0].string.strip()
				span_array = message.findAll('div', attrs={'class':'gc-message-message-display'})[0].findAll('span', attrs={'class':'gc-word-high'})
				voicemail_transcript_array = []
				for word in span_array:
					voicemail_transcript_array.append(word.string.strip())
				voicemail_transcript = ' '.join(voicemail_transcript_array)
				identifier = from_name + ' ' + voicemail_transcript
				if identifier not in self.convo_threads[id]:
					self.convo_threads[id].add(identifier)
					if from_name != 'Me':
						if self.listeners and len(self.listeners) > 0:
							for listener in self.listeners:
								listener.on_notification('Voicemail', from_name, voicemail_transcript)

	def generate_sms_key(self, from_name, text, time):
		return '%s__BREAKER__%s__BREAKER__%s' % (from_name, text, time)
		
	def check(self):
		feed = self.get_inbox()
		feed = feed.replace("<![CDATA[", "")
		feed = feed.replace("]]>", "")
		self.parse_result(feed)
		# I don't want to parse voicemails for now
		# vmfeed = self.get_voicemails()
		# vmfeed = vmfeed.replace("<![CDATA[", "")
		# vmfeed = vmfeed.replace("]]>", "")
		# self.parse_voicemails(vmfeed)
		out_fl = open(self.picklefile, 'w')
		pickle.dump(self.read_sms_messages, out_fl)
		out_fl.close()
