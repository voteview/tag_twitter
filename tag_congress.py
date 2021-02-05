# New schema ready except party name lookup
import requests
import os
from datetime import datetime
from fuzzywuzzy import fuzz
import shutil
from pymongo import MongoClient
import sys
import re
import bs4
import sqlite3
sys.path.append('/var/www/voteview/')
from model.searchParties import partyName
from model.stateHelper import stateName


def get_ordinal(number):
	ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])
	return ordinal(number)

def get_labels(res):
	if not "state_abbrev" in res or not "district_code" in res:
		return [partyName(res["party_code"])]

	label1 = "%s-%s" % (res["state_abbrev"], str(res["district_code"]).zfill(2))
	label2 = "%s%s" % (res["state_abbrev"], str(res["district_code"]).zfill(2))
	label3 = get_ordinal(res["district_code"])

	return [label1, label2, label3]


connection = MongoClient()
db = connection["voteview"]

conn = sqlite3.connect("data/verified_users")
conn.row_factory = sqlite3.Row
c = conn.cursor()

i=0
curICPSR = []

# Get all the results we have to deal with and iterate through them.
result_cursor = [row for row in db.voteview_members.find({'congress': {'$gt': 109}, 'twitter': {'$exists': False}},{"fname": 1, "bioname": 1, "name": 1, "congress": 1, "icpsr": 1, "party_code": 1, "district_code": 1, "state_abbrev": 1, "_id": 0}, no_cursor_timeout=True).sort([("congress", -1), ("icpsr", 1)])]
for index, res in enumerate(result_cursor):
	# We have multiple rows per ICPSR, so once we've seen someone once we don't need to see them again
	if res["icpsr"] in curICPSR:
		continue
	curICPSR.append(res["icpsr"])

	# What's our highest quality name data?
	try:
		lastname = re.sub(r"[^a-zA-Z ']+", '', res["bioname"].split(",",1)[0]).lower()
		name = res["bioname"]
		firstName = re.sub(r"[^a-zA-Z ']+", '', res["bioname"].split(",",1)[1]).lower()
	except:
		try:
			lastname = re.sub(r"[^a-zA-Z ']+", '', res["fname"].split(",",1)[0]).lower()
			name = res["fname"]
			firstname = re.sub(r"[^a-zA-Z ']+", '', res["fname"].split(",",1)[1]).lower()
		except:
			continue

	cqlabel = get_labels(res)

	# Left pad ICPSR number to 6 digits
	icpsrPad = str(res["icpsr"]).zfill(6)

	# Check Twitter candidates
	c.execute("SELECT name, username, location, bio, followers FROM twitter_users WHERE name LIKE ? COLLATE NOCASE OR bio LIKE ? COLLATE NOCASE ORDER BY followers DESC;", ["%"+lastname+"%", "%"+lastname+"%"])
	results = c.fetchall()
	resultSet = []

	newResults = []
	goodResults = 0
	maxScore = 0
	for twitResult in results:
		modResult = dict(zip(twitResult.keys(), twitResult))
		modResult["score"] = fuzz.token_set_ratio(twitResult["name"].lower(), name)
		if any(x in twitResult["bio"].lower() or x in twitResult["name"].lower() for x in ["rep.","representative","sen.","senator","governor","gov.", "congress", "district"]):
			modResult["score"] = modResult["score"] + 50
		if modResult["followers"] < 5000:
			modResult["score"] = modResult["score"] - 20
		if res["state_abbrev"].lower() in twitResult["bio"].lower():
			modResult["score"] = modResult["score"] + 10

		if modResult["score"] > 100 and not goodResults:
			modResult["score"] = modResult["score"] + 20
		if any([x.lower() in modResult["bio"].lower() for x in cqlabel]):
			modResult["score"] = modResult["score"] + 20

		maxScore = max(maxScore, modResult["score"])
		if modResult["score"] > 100:
			goodResults = goodResults + 1
		newResults.append(modResult)

	newResults.sort(key=lambda x: -x["score"])

	i = 1
	print("%s / %s: Which of these is the twitter account for %s (%s). ICPSR %s? " % (index, len(result_cursor), name, cqlabel[0], icpsrPad))
	for twitResult in newResults:
		if twitResult["score"] > maxScore / 2:
			resultSet.append(twitResult["username"])
			print("%s)\t%s\t%s\t%s\t%s followers" % (i, twitResult["name"], twitResult["username"], twitResult["location"], twitResult["followers"]))
			print("Name score match: %s" % twitResult["score"])
			print(twitResult["bio"])
			print("=======")
			i = i + 1
		if len(resultSet) > 7:
			break

	if not resultSet:
		continue

	if len(resultSet) < len(newResults):
		print str(len(newResults)-len(resultSet)) + " matches that seemed to be low quality."

	selected = False
	quit = 0
	while not selected:
		print "Enter a number or type N to confirm no match found or type Q to quit."
		print "Which of these is the twitter account for "+name+" " + cqlabel[0] + ". ICPSR code: "+icpsrPad+"?  ",
		whichOne = raw_input()
		try:
			selectedNum = int(whichOne)-1
			if selectedNum < 0 or selectedNum >= len(resultSet):
				print "Invalid selection, please select from 1-"+str(len(resultSet))+" or press N for no match found."
			else:
				selected = True
		except:
			if whichOne.lower() == "n":
				print "Confirmed no match."
				db.voteview_members.update({"icpsr": res["icpsr"]}, {"$set": {"twitter": ""}}, upsert=False, multi=True)
				os.system('clear')
				break
			elif whichOne.lower() == "q":
				quit = 1
				break
			else:
				print "Invalid selection, please select from 1-" + str(len(resultSet)) + " or press N for no match found."

	if quit:
		sys.exit(-1)
	os.system('clear')

	if selected:
		db.voteview_members.update({"icpsr": res["icpsr"]}, {"$set": {"twitter": resultSet[selectedNum], "last_updated": datetime.utcnow()}}, upsert=False, multi=True)
