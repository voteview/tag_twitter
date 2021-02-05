import json
import tweepy
import pprint
import sys
import sqlite3
import requests
import urllib
requests.packages.urllib3.disable_warnings()

# Initial login / setup
authData = json.load(open("config/auth.json","r"))
consumer_key = authData["consumer_key"]
consumer_secret = authData["consumer_secret"]
access_token = authData["access_token"]
access_token_secret = authData["access_token_secret"]
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth,wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

conn = sqlite3.connect("data/verified_users")
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS twitter_users (id INTEGER UNIQUE, name TEXT, username TEXT, url TEXT, location TEXT, bio TEXT, followers INTEGER, processed INTEGER);")
conn.commit()

scrape_accounts = 1
# OK start scraping
if scrape_accounts:
	ids = []
	i=0
	for friend in tweepy.Cursor(api.friends_ids, screen_name="verified").items():
		print(friend)
		ids.append(friend)
		c.execute("INSERT OR IGNORE INTO twitter_users (id) VALUES (?)", (friend,))
		if i%10==0:
			print(".")
			conn.commit()
		if i%1000==0:
			print("!")
		i=i+1
	conn.commit()
else:
	ids = []
	c.execute("SELECT id FROM twitter_users WHERE processed IS NULL;")
	data = c.fetchall()
	for d in data:
		ids.append(d[0])

print len(ids)

def userBatch(idQueue):
	global c, conn
	users = api.lookup_users(user_ids=idQueue, include_entities=1)
	for user in users:
		ud = user._json
		name = "name" in ud and ud["name"] or "No Name"
		screen_name = "screen_name" in ud and ud["screen_name"] or "No Screen Name"
		url = "url" in ud and ud["url"] or ""

		followers_count = "followers_count" in ud and int(ud["followers_count"]) or 0
		location = "location" in ud and ud["location"] or ""
		description = "description" in ud and ud["description"] or ""

		print("%s\%s\%s\%s\%s" % (name, screen_name, url, followers_count, location))
		c.execute("UPDATE twitter_users SET name=?,username=?,url=?,location=?,bio=?,followers=?,processed=1 WHERE id=?",[name, screen_name, url, location, description, followers_count, ud["id"]])

	conn.commit()
	return

get_account_info = 1
if get_account_info:
	idQueue = []
	for id in ids:
		idQueue.append(id)
		if len(idQueue) == 100:
			userBatch(idQueue)
			idQueue = []
	userBatch(idQueue)


