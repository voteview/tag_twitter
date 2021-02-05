""" Tag members of congress with Twitter fields based on best matches. """
from builtins import input
from datetime import datetime
import argparse
import csv
import os
import re
import sqlite3
from fuzzywuzzy import fuzz
from pymongo import MongoClient
from tqdm import tqdm


def connect_db():
    """ Connect to DB """
    connection = MongoClient()
    mongo_db = connection["voteview"]

    conn = sqlite3.connect("data/verified_users")
    conn.row_factory = sqlite3.Row
    sqlite_db = conn.cursor()

    return mongo_db, sqlite_db, conn


def get_ordinal(number):
    """
    Quick map of number to ordinal for checking bios. e.g. 2 -> 2nd
    """
    ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(n//10%10!=1)*(n%10<4)*n%10::4])
    return ordinal(number)


def get_labels(res):
    """ Get all possible ways of saying district name. """
    if "state_abbrev" not in res or "district_code" not in res:
        return [""]

    label1 = (
        "%s-%s" % (res["state_abbrev"], str(res["district_code"]).zfill(2))
    )
    label2 = "%s%s" % (res["state_abbrev"], str(res["district_code"]).zfill(2))
    label3 = get_ordinal(res["district_code"])

    return [label1, label2, label3]


def identify_all(min_congress=109):
    """
    Extract all members starting with a certain congress who do not yet have
    a Twitter handle
    """

    mongo_db, sqlite_db, conn = connect_db()

    seen_icpsrs = []
    result_cursor = [
        row for row in mongo_db.voteview_members.find(
            {
                'congress': {'$gt': min_congress - 1},
                'twitter': {'$exists': False}},
            {
                "fname": 1, "bioname": 1, "name": 1, "congress": 1,
                "icpsr": 1, "party_code": 1, "district_code": 1,
                "state_abbrev": 1, "_id": 0},
            no_cursor_timeout=True).sort([("congress", -1), ("icpsr", 1)])]

    for index, res in enumerate(tqdm(result_cursor)):
        # Make sure we only see a given ICPSR one time.
        if res["icpsr"] in seen_icpsrs:
            continue
        seen_icpsrs.append(res["icpsr"])

        os.system("clear")
        result_tagged = identify_single(res, sqlite_db)

        # No possible candidates, skip.
        if not result_tagged["input"]:
            continue

        # User is fed up, time to quit.
        if result_tagged["input"] == "q":
            break

        mongo_db.voteview_members.update(
            {"icpsr": res["icpsr"]},
            {"$set":
                {
                    "twitter": result_tagged["output"],
                    "last_updated": datetime.utcnow()
                }},
            upsert=False, multi=True
        )

    print("OK, Done.")


def identify_single(person, sqlite_db):
    """
    Allow user to identify a single Twitter account for a single
    congressperson.
    """
    # Get district label, pad ICPSR left to six digits.
    cqlabel = get_labels(person)
    candidates = get_candidates(person, cqlabel, sqlite_db)

    # Ask the user which is right and finish up
    if candidates:
        output = process_selection(person, cqlabel, candidates)
        return output

    # No one was even a potential candidate, so let's leave this mystery
    # unsolved for now.
    return {"input": "", "output": ""}


def get_candidates(person, cqlabel, sqlite_db):
    """ Which Twitter accounts have a person's last name? """
    # If we don't have a proper bio name, it's a DB issue and skip them.
    if "bioname" not in person:
        return []

    # Extract last name from person we're looking at
    last_name = re.sub(
        r"[^a-zA-Z '\-]+", "",
        person["bioname"]).split(",", 1)[0].lower()

    # Who even has the person's last name?
    sqlite_db.execute(
        """
        SELECT name, username, location, bio, followers FROM twitter_users
        WHERE name LIKE ? COLLATE NOCASE OR bio LIKE ? COLLATE NOCASE
        ORDER BY followers DESC;
        """,
        [f"%{last_name}%", f"%{last_name}%"]
    )
    results = sqlite_db.fetchall()

    # Score every candidate.
    candidate_results = [
        score_cand(person, cqlabel, result) for result in results
    ]

    # Return in descending score length.
    candidate_results.sort(key=lambda x: -x["score"])

    return candidate_results


def score_cand(person, cqlabel, result):
    score = fuzz.token_set_ratio(result["name".lower()], person["bioname"])

    if (any(x in result["bio"].lower() or x in result["name"].lower() for x in
            [
                "rep.", "representative", "sen.", "senator", "governor",
                "gov.", "congress", "district", "democrat", "republican",
                "gop", "dnc", "rnc"
            ])):
        score = score + 50

    if result["followers"] < 5000:
        score = score - 20

    if person["state_abbrev"].lower() in result["bio"].lower():
        score = score + 10

    if cqlabel and any(x.lower() in result["bio"].lower() for x in cqlabel):
        score = score + 20

    result["score"] = score
    return result


def process_selection(person, cqlabel, candidates):
    """ Presents user with candidates and gets their input. """
    max_score = candidates[0]["score"]

    # Prompt for what the user is working on.
    print(
        "Please select the correct Twitter account, if any, for %s (%s)\n\n" %
        (person["bioname"], cqlabel[0])
    )

    good_candidates = 0
    for index, candidate in enumerate(candidates):
        # Only show 8 candidates, and only show good candidates
        if candidate["score"] < max_score / 2 or index > 7:
            break
        good_candidates = good_candidates + 1

        print((
            "%s)\t %s\t%s\n%s\t%s\n%s\n\nScore: %s\n=====" %
            (index, candidate["username"], candidate["name"],
             candidate["location"], candidate["followers"],
             candidate["bio"], candidate["score"])))

    # Tell the user how many crummy candidates existed.
    if good_candidates < len(candidates):
        print((
            "... plus %s low-quality results" %
            (len(candidates) - good_candidates)))

    # Fill in the selected user, if there was one.
    select_template = input_selection(good_candidates)
    if select_template["input"] not in ["n", "q"]:
        select_template["output"] = (
            candidates[int(select_template["input"])]["username"]
        )

    return select_template


def input_selection(number_candidates):
    """ Just a raw input handler. """

    valid_inputs = (
        [str(x + 1) for x in range(number_candidates)] +
        ["n", "q"]
    )

    print(
        "\nSelect an option from 1-%s, 'N' for no result, 'Q' for quit." %
        (number_candidates + 1))
    user_input = input("> ")
    while user_input.lower() not in valid_inputs:
        print("Invalid input.")
        print(
            "Select an option from 1-%s, 'N' for no result, 'Q' for quit." %
            (number_candidates + 1))
        user_input = input("> ")

    return {"input": user_input, "output": ""}


def do_archive():
    mongo_db, _, _ = connect_db()

    results = mongo_db.voteview_members.find(
        {"twitter": {"$exists": True}},
        {"icpsr": 1, "bioname": 1, "congress": 1, "chamber": 1, "twitter": 1}
    )

    with open("data/archive_results.csv", "w") as csv_file:
        headers = ["icpsr", "bioname", "congress", "chamber", "twitter"]
        writer = csv.DictWriter(
            csv_file, fieldnames=headers, extrasaction="ignore"
        )
        writer.writeheader()
        for result in results:
            writer.writerow(result)


def parse_arguments():
    """ Execute main functions. """
    parser = argparse.ArgumentParser(
        description="Matches congresspersons to Twitter accounts"
    )
    parser.add_argument(
        "--min_congress", type=int, default=109,
        help="Minimum congress to check (default 109)")
    args = parser.parse_args()

    identify_all(args.min_congress)


if __name__ == "__main__":
    parse_arguments()
    do_archive()
