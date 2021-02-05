""" Scrapes verified users using Twitter API to prep for matching later. """

from __future__ import print_function
import json
import argparse
import sqlite3
import tweepy


def connect_api():
    """ Load config and use tweepy to connect to API. """
    auth_data = json.load(open("config/auth.json", "r"))
    auth = tweepy.OAuthHandler(
        auth_data["consumer_key"], auth_data["consumer_secret"]
    )
    auth.set_access_token(
        auth_data["access_token"], auth_data["access_token_secret"]
    )
    api = tweepy.API(
        auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True
    )

    conn = sqlite3.connect("data/verified_users")
    db = conn.cursor()

    db.execute(auth_data["table_spec"])
    conn.commit()

    return api, db, conn


def scrape_raw_verified(api, db, conn):
    """ Who is the @verified account following? """
    ids = []
    for fid in tweepy.Cursor(api.friends_ids, screen_name="verified").items():
        ids.append(fid)
        db.execute(
            "INSERT OR IGNORE INTO twitter_users (id) VALUES (?)",
            (fid,))

        if not len(ids) % 10:
            conn.commit()

    conn.commit()
    return ids


def load_unhydrated(db):
    """ Load all unhydrated IDs from the SQLite database. """
    db.execute("SELECT id FROM twitter_users WHERE processed IS NULL;")
    data = db.fetchall()
    return [d[0] for d in data]


def batch_hydrate(all_ids, api, db, conn):
    """ Split full ID list into batches of 100 and hydrate them. """

    batches = [all_ids[i:i + 100] for i in range(0, len(all_ids), 100)]
    for index, batch in enumerate(batches):
        print("  Processing batch %s" % index)
        hydrate_users(batch, api, db, conn)


def hydrate_users(ids, api, db, conn):
    """ Hydrate the unhydrated users specified in `ids`"""
    try:
        users = api.lookup_users(user_ids=ids, include_entities=1)
    except tweepy.TweepError:
        print("Error completing user lookup; no results found.")
        return

    for user in users:
        user_json = user._json
        user_id = user_json["id"]
        name = user_json.get("name", "No Name")
        screen_name = user_json.get("screen_name", "No Screen Name")
        url = user_json.get("url", "")
        followers = int(user_json.get("followers_count", 0))
        location = user_json.get("location", "")
        description = user_json.get("description", "")

        print("%s (@%s, %s followers)\n%s\n%s" %
              (name, screen_name, followers, location, description))

        db.execute(
            """
            UPDATE twitter_users SET name = ?, username = ?, url = ?,
            location = ?, bio = ?, followers = ?, processed = 1,
            WHERE id = ?;
            """,
            [name, screen_name, url,
             location, description, followers, user_id]
        )

    conn.commit()


def delete_non_us(db, conn):
    """ Remove all non-US accounts to reduce size of data. """

    non_us_locations = (
        [unicode(x.trim()) for x in
         open("config/non_us_locations.txt", "r").readlines()
         if x.trim()])

    for location in non_us_locations:
        db.execute("DELETE FROM twitter_users WHERE location = ?", (location, ))
    conn.commit()

def parse_arguments():
    """ Execute main functions. """
    parser = argparse.ArgumentParser(
        description="Gathers a list of verified accounts on Twitter"
    )
    parser.add_argument("--rescan", help="Manually rescan verified users")
    args = parser.parse_args()

    api, db, conn = connect_api()
    if args.rescan:
        print("Scraping verified users...")
        ids = scrape_raw_verified(api, db, conn)
    else:
        print("Loading unhydrated users from db...")
        ids = load_unhydrated(db)

    if ids:
        print("%s users to process" % len(ids))
        batch_hydrate(ids, api, db, conn)

    print("Deleting non-us users...")
    delete_non_us(db, conn)

    print("Defragmenting database...")
    db.execute("VACUUM")
    conn.commit()

    print("OK, done.")


if __name__ == "__main__":
    parse_arguments()
