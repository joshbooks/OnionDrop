#! /bin/python2

#all python modules (stem, flask, flask-bootstrap, psycopg2, 
#boto, flask-nav, flask-wtf, and apscheduler so far)
#installed with pip, which was installed with easy install.
#Easy install was installed through pacman.
#Depending on linux distro the exeutable may be named
#easy_install-X.Y, for me on arch it was easy_install-2.7 
#additionally postgresql and the pg_config executable,
#for me it was in postgresql-libs
#and the databases were set up using psql
#I will not be giving a database tutorial

###########################
##Begin Main Control Flow##
###########################
import json
import time
import re
import os
import psycopg2
import atexit
import logging
import tarfile
import random
import string

from stem.descriptor import reader
from stem.control import Controller
from flask import Flask, send_file, request, render_template, flash
from flask_bootstrap import Bootstrap
from flask_appconfig import AppConfig
from flask_wtf import Form
from wtforms import TextField, ValidationError, SubmitField
from apscheduler.schedulers.background import BackgroundScheduler
from Crypto.PublicKey import RSA
from boto.s3.connection import S3Connection

#navbar imports
from flask_nav import Nav
from flask_nav.elements import Navbar, View


#TODO change to flask-appconfig
from Config import get_awsAccessKey, get_awsSecretKey, get_dbName, get_dbUser, get_dbPW, get_dbAddr, get_dbPort, get_hidden_svc_dir, get_devKey

from forms import DropForm, GoDrop, GetPack, GetAbout

#TODO now that I've debugged the database connection stuff pretty
#thoroughly, I can just inline the db insert instead of calling a function
#Define function to add encrypted message to database
def addMail(hs, encMsg):
	print "trying to add mail"
	cur.execute("INSERT INTO msgs (onion, msg) VALUES(%s, %s);", (hs, psycopg2.Binary(encMsg)))
	print "Just added msg"

#TODO since the ec2 instance starts up blank we'll need to store most of the stuff in an s3 bucket
#and then as an argument/input file we just take the aws access key and secret key
#Things that will need saving in s3:
#config info
#hidden service directory
#torrc (exclusively for relaying, all hosting/network config gets done through stem)



#begin tor bit
print "about to open control connection to tor"
controller = "opening controller failed"
try:
	controller = Controller.from_port()
	controller.authenticate()
except Exception as e:
	print e
	print "tor is not letting us authenticate, is it configured correctly and running?" 
	exit()

print "successfully opened control connection to tor"


#begin apscheduler bit
print "beginning scheduler dameon"
cron = BackgroundScheduler()
cron.start()
print "succesfully began scheduler daemon"


# begin flask bit
print "now entering flask section"
app = Flask(__name__)
port = 5000
host = "127.0.0.1"

#begin bootstrap/appconfig bit
#AppConfig(app, None)#configFile arg is deprecated
Bootstrap(app)

#begin database bit
conn = psycopg2.connect("host = %s port = %s dbname=%s user=%s password = %s"%(get_dbAddr(), get_dbPort(), get_dbName(), get_dbUser(), get_dbPW()))
conn.autocommit = False
cur = conn.cursor()

#Begin boto bit
botoConn = S3Connection(get_awsAccessKey(), get_awsSecretKey())
botoMsgs = botoConn.get_bucket("msgpacks")

#begin navbar stuff
nav = Nav()

@nav.navigation()
def mynavbar():
    return Navbar(
        'OnionDrop',
        View('Home', 'index')
    )

nav.init_app(app)

##################################
##Define function to run at exit##
##################################
def graceful():
	try:
		cron.shutdown()
	except Exception as e:
		print "Could not shut down background scheduler, got the following exception:"
		print e

	try:
		cur.close()
	except Exception as e:
		print "Could not close database cursor, got the following exception:"
		print e

	try:
		conn.close()
	except Exception as e:
		print "Could not close database connection, got the following exception:"
		print e

	try:
		controller.remove_hidden_service(get_hidden_svc_dir(), 80)
	except Exception as e:
		print "Could not remove hidden service"
		print e

	try:
		controller.close()
	except Exception as e:
		print "Could not close control connection to hidden service"
		print e 


atexit.register(graceful)
##########################
##Define Background Jobs##
##########################

def packUp():
	print "packing up the database"

	while True:
		print "now starting database packing loop"
		#Get some .onion address with queued messages
		cur.execute("SELECT onion FROM msgs LIMIT 1;")
		someRow = cur.fetchone()

		#since we select whatever happens to be first
		#if that's null then the database is empty
		#and we're done
		if someRow is None:
			print "No database to pack up :)"
			return
		hs = someRow[0]
		
		print hs+" is the hidden service this message was directed to"

		cur.execute("SELECT * FROM msgs WHERE onion = %s;", (hs,))

		if cur.rowcount <= 0:
			print "something fishy happened with the database D:"
			exit()

		#TODO depending on whether it's a bucket or key method we'll either
		#check here or in the very beginning of the if block to see
		#if there are any ongoing processes or just generally to see
		#if there's some reason not to download right now
		key = botoMsgs.get_key("msgpacks/"+hs+".tar.gz")
		if key is not None:
			#to do this asynchronously set the res_download_handler argument
			key.get_contents_to_filename('msgpacks/'+hs+".tar.gz")
		else:
			print "msgpack did not have an existing msgpack for that hidden service"
		

		#Set up the temporary tarfile to write to
		tmp = tarfile.open(name="msgpacks/"+hs+".tmp.tar.gz", mode='w:gz')
		names=[]

		#get all rows in the message database for this onion
		rows = cur.fetchall()

		#write them all to file and add them to the .tmp.tar.gz
		for row in rows:
			print row
			thisName = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(14))
			stupidHack = open(thisName, 'w+')
			stupidHack.write(str(row[1]))
			stupidHack.close()
			tmp.add(thisName)
			names=names+[thisName]
			cur.execute("DELETE FROM msgs WHERE msg = %s;", (row[1],))

		conn.commit()

		#depending on how multithreaded/asynchronous/atomic we're going to get
		#here it might make sense to keep this if the way it is, or it might make more
		#sense to change it to an exception/error/log event inside an if not
		if key is not None:
			old = tarfile.open('msgpacks/'+hs+".tar.gz", mode='r:gz')
			old.extractall()
			for member in old.getmembers():
				tmp.add(member.name)
				names=names+[member.name]
			old.close()

		tmp.close()

		for i in names:
			os.remove("./"+i)


		#This is ok on linux but can raise an uncaught exception
		#on windows
		#Otherwise I'm moderately proud of this lazy atomicity
		if os.path.isfile("msgpacks/"+hs+".tar.gz"):
			os.remove("msgpacks/"+hs+".tar.gz")
		
		os.rename("msgpacks/"+hs+".tmp.tar.gz", "msgpacks/"+hs+".tar.gz")

		#I am going to do the thing I hate to do, here is the upload code
		#that I am actually going to use unless something awesome occurs to me.
		#it is not thread safe, it is not atomic, it may well cause problems
		#with certain use cases, it is not good, but here it is
		#we just upload the file then delete it locally
		#From what I've heard s3 behaves well enough that this is pretty
		#allowable, but it is not code that I would like to keep indefinitely
		#some actually good solution would be quite nice, even if it is s3fs

		#arguably simpler not to do this check and instead
		#blindly write with a force flag on, but this way
		#should generate less network
		#activity which is capital G Good

		if key is None:
			key = botoMsgs.new_key(key_name="msgpacks/"+hs+".tar.gz")

		key.set_contents_from_filename("msgpacks/"+hs+".tar.gz")

		os.remove("msgpacks/"+hs+".tar.gz")


cron.add_job(packUp, 'interval', minutes=30, max_instances=1)

#amazon's linux distro automatically logrotates
#which causes tor to get a hup signal, so this will
#definitely be good to run every day, but 
def checkTor():
	if not controller.isAlive():
		print "tor controller was dead, now trying to restart it"
		try:
			controller = Controller.from_port()
			controller.authenticate()
		except Exception as e:
			print e
			print "tor is not letting us authenticate, is it configured correctly and running?" 
			exit()

		print "successfully opened control connection to tor"
#TODO here and elsewhere we should change from the get_conf/set_options
#interface to the create_ephemeral_hidden_service/
#remove_ephemeral_hidden_service/list_ephemeral_hidden_services
#that way we can also put the key and hostname in config and not have to
#worry about setting up /var/lib/tor/hidden_service

	if controller.get_conf("HiddenServiceDir") is None:
		print "tor was not configure to provide a hidden service, now configuring"
		try:
			controller.set_options([
			("HiddenServiceDir", get_hidden_svc_dir()),
			("HiddenServicePort", "80 %s:%s" % (host, str(port)))
			])
		except Exception as e:
			print "unable to create hidden service"
			print e
			quit()

cron.add_job(checkTor, 'interval', minutes=30, max_instances=1)

#########################
##Define Response Pages##
#########################

def index():
	if request.method == 'GET':
		return render_template('index.html', form1=GoDrop(), form2=GetPack(), form3=GetAbout())

	hs = request.form['field1']

	#validators should handle this for our page
	#but raw post could still mess with us here
	if (hs is None) or (hs == ""):
		return "<h1>please enter all required fields</h1>"

	if not (re.match("\w+\.onion", hs)):
		if re.match("http://", hs):
			hs = hs[7:]
		if re.match("https://", hs):
			hs = hs[8:]
		if re.match("\w+.onion/", hs):
			hs = hs[:-1]
		if not (re.match("\w+\.onion", hs)):
			if re.match("\w+", hs):
				hs=hs+".onion"
			else:
				return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>"+hs+" is not a valid .onion url, try again</h1>You will be redirected to the homepage in 5 seconds'


	key = botoMsgs.get_key("msgpacks/"+hs+".tar.gz")
	if key is None:
		return """
			<h1>Sorry, it looks like there is no mail for that hidden service</h1>
			<h2> Alternately you may have hit a glitch, in whch case trying again would be advisable<h2>
			<h3> But I'm not trying to run your life or anything, you do you</h3> 
		"""


	return '<meta HTTP-EQUIV="REFRESH" content="5; url=%s"><h1> you will be redirected to your download in 5 seconds</h1><a href="/">Click here for the homepage or press your browser back button'% key.generate_url(expires_in=360, query_auth=False)

app.add_url_rule('/', 'index', index, methods=("POST", "GET"))

def dropPage():
	return render_template('drop.html', form=DropForm())

app.add_url_rule("/drop/", 'dropPage', dropPage)

def aboutPage():
	return render_template('about.html')

app.add_url_rule("/about/", 'aboutPage', aboutPage)

def sitOn():
	print "attempted to post new message"
	hs = request.form['field1']
	msg = request.form['field2']

	if (hs is None) or (msg is None) or (msg == '') or (hs == ""):
		return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>please enter all required fields</h1>You will be redirected the home page in 5 seconds'
	if not (re.match("\w+\.onion", hs)):
		if re.match("http://", hs):
			hs = hs[7:]
		if re.match("https://", hs):
			hs = hs[8:]
		if re.match("\w+.onion/", hs):
			hs = hs[:-1]
		if not (re.match("\w+\.onion", hs)):
			if re.match("\w+", hs):
				hs=hs+".onion"
			else:
				return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>"+hs+" is not a valid .onion url, try again</h1>You will be redirected to the homepage in 5 seconds'


	#TODO more rigorous way of determining whether or not message is already encrypted
	if (re.match("\w*BEGIN PGP MESSAGE\w*", msg) and re.match("\w*END PGP MESSAGE\w*", msg)) or (re.match("\w*BEGIN RSA MESSAGE\w*", msg) and re.match("\w*END RSA MESSAGE\w*", msg)):
		addMail(hs, msg)
		return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>Mail has been dropped</h1>You will be redirected to the homepage in 5 seconds'


	cur.execute("SELECT key FROM keys WHERE onion = %s", (hs,))
	result = cur.fetchone()
	conn.commit()

	if result:
		psk = result[0]

	if not result:
		desc = 'bogus'

		try:
			desc = controller.get_hidden_service_descriptor(hs)
		except Exception as e:
			print e
			desc = 'bogus'

		if desc == 'bogus':
			return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>we couldn\'t get the hidden service descriptor for the hidden service '+hs+'</h1>You will be redirected to the homepage in 5 seconds'

		print desc
		psk = str(desc.permanent_key)
		print psk
		
		cur.execute("INSERT INTO keys (onion, key) VALUES(%s, %s);", (hs, psycopg2.Binary(psk)))
		conn.commit()

	psk = RSA.importKey(psk)

	encMsg = psk.encrypt(str(msg), 32)

	addMail(hs, encMsg[0])

	return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>Mail has been encrypted and dropped</h1>You will be redirected to the homepage in 5 seconds'


app.add_url_rule("/newmsg", 'sitOn', sitOn, methods=["POST"])

def retKey(hs):
	
	if not (re.match("\w+\.onion", hs)):
		if re.match("http://", hs):
			hs = hs[7:]
		if re.match("https://", hs):
			hs = hs[8:]
		if re.match("\w+.onion/", hs):
			hs = hs[:-1]
		if not (re.match("\w+\.onion", hs)):
			if re.match("\w+", hs):
				hs=hs+".onion"
		else:
			return '<meta HTTP-EQUIV="REFRESH" content="5; url=/"><h1>"+hs+" is not a valid .onion url, try again</h1>You will be redirected to the homepage in 5 seconds'

	cur.execute("SELECT key FROM keys WHERE onion = %s", (hs,))
	result = cur.fetchone()
	conn.commit()

	if result:
		psk = result[0]
		print "got key from database"

	if not result:
		print "couldn't get key from database"
		desc = 'bogus'

		try:
			print "about to get hidden service descriptor"
			desc = controller.get_hidden_service_descriptor(hs)
		except Exception as e:
			print e
			desc = 'bogus'
		print "successfully got hidden service descriptor"
		if desc == 'bogus':
			return "<h1>we couldn't get the hidden service descriptor for the hidden service "+hs+"</h1>"

		psk = str(desc.permanent_key)
		
		cur.execute("INSERT INTO keys (onion, key) VALUES(%s, %s);", (hs, psycopg2.Binary(psk)))
		conn.commit()

	return str(psk)

app.add_url_rule("/key/<hs>/", 'retKey', retKey)

######################################################
##All other URL classes should come before this one ##
##As this one will match anything the others don't  ##
######################################################
#@app.route("/<hs>/")
def msgPage(hs):

	if (hs is None) or (hs == ''):
		return "It looks like you have discovered a unicode issue with flask, not with this site though :)"

	if not (re.match("\w+\.onion", hs)):
		if re.match("\w+", hs):
			hs=hs+".onion"
		else:
			return "<h1>"+hs+" is not a valid .onion url, try again</h1>"

	#check if the msgpack exists in our msgpacks bucket
	key = botoMsgs.get_key("msgpacks/"+hs+".tar.gz")
	if key is None:
		return """
			<h1>Sorry, it looks like there is no mail for that hidden service</h1>
			<h2> Alternately you may have hit a glitch, in whch case trying again would be advisable<h2>
			<h3> But I'm not trying to run your life or anything, you do you</h3> 
			"""

	#for the pretty site this will likely turn into a fancy html5 download link
	return '<meta HTTP-EQUIV="REFRESH" content="5; url=%s"><h1> you will be redirected to your download in 5 seconds</h1>'% key.generate_url(expires_in=360, query_auth=False)
	#TODO make super double sure it plays nice with tor, also make sure 
	#it consistently downloads as attachment, otherwise we'll do the custom header thing to make sure it does

app.add_url_rule("/<hs>/", 'msgPage', msgPage)

############################
##Resume Main Control Flow##
############################

print "about to try creating hidden service"
try:
	controller.set_options([
	("HiddenServiceDir", get_hidden_svc_dir()),
	("HiddenServicePort", "80 %s:%s" % (host, str(port)))
	])
except Exception as e:
	print "unable to create hidden service"
	print e
	quit()

print "about to start flask"


app.config['SECRET_KEY'] = get_devKey()


#never enable on a production server
#app.debug = True

app.run()

