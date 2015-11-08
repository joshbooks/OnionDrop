#! /bin/python2

import xmlrpclib
import json
import time
import base64

from stem.util import conf
from stem.descriptor.hidden_service_descriptor import HiddenServiceDescriptor as HSD

#TODO check and see if bm is already running with api enabled
#if not handle it

api = xmlrpclib.ServerProxy("http://bitmessage:security@localhost:8442/")

#should take torrc path as argument, hardcoded for testing purposes
torrc = '/etc/tor/torrc'

hiddenConfig = conf.config_dict('hidden_config', {
'HiddenServiceDir' : '/this/is/nonsense'
})

myTor = conf.get_config('hidden_config')

try:
	myTor.load(torrc)
except IOError as exc:
	print "Unable to load the user's config: %s" % exc
	quit()


dirs = myTor.get('HiddenServiceDir')

if type(dirs) is str:
	if dirs == '/this/is/nonsense':
		print 'torrc is not configured correctly, please fix before proceeding'
		quit()
	dirs = (dirs,)
elif (type(dirs) is not list) and (type(dirs) is not tuple):
	print 'torrc is not configured correctly, please fix before proceeding'
	quit()

#so we're pretty solid up to here

iter = 0
hiddenServiceKeys = 'bogus'
#need to test this, I'm not sure if it's ok with taking the directory as "raw_contents"
#will not work with "stealth authorization" since in that scheme
#the hidden service does not provide a public key

for dir in dirs:
	if iter == 0:
		hiddenServiceKeys = (HSD(dir).permanent_key,)
		iter = 1
	else:
		hiddenServiceKeys = hiddenServiceKeys + (HSD(dir).permanent_key,)
	
#alternately, it may turn out to be easier to use the raw conf reader
#just need to find out the format
#for reading key file(s)
#keyConfig = conf.config_dict('key_config', {

if hiddenServiceKeys == 'bogus':
	print 'torrc seems to be configured correctly, but we couldn't parse the Hidden Services directory/ies'
	print 'Have you restarted tor since you configured your hidden service?'
	quit()

iter = 0
channels = 'bogus'

for psk in hiddenServiceKeys:
	channel = api.createChan(base64.b64encode(psk))

	if channel == 'API Error 0024: Chan address is already present.':
		for i in json.loads(api.listAddresses2())['addresses']:
			if base64.b64decode(i['label']) == "[chan] "+psk:
				channel = i['address']

	if iter == 0:
		channels = (channel,)
		iter = 1
	else:
		channels = channels + (channel,)

if hiddenServiceKeys == 'bogus':
	print 'torrc seems to be configured correctly, and we parsed the Hidden Services directory/ies'
	print 'but we couldn't generate/find the necessary address(es)'
	print 'is something wrong with bitmessage?'
	quit()

while True:
	for i in json.loads(api.getAllInboxMessages())['inboxMessages']:
		for channel in channels:
			if i['toAddress'] == channel and base64.b64decode(i['subject']) == 'ToHSO':
				if i['read'] == 0:
					print base64.b64decode(i['message'])


