""" Overwrites database Twitter handles with file Twitter handles. """

import csv
from datetime import datetime
from pymongo import MongoClient
from tqdm import tqdm

def import_all():
    """ Overwrites database Twitter handles with file Twitter handles. """

    connection = MongoClient()
    db = connection["voteview"]

    with open("data/archive_results.csv", "r") as csv_read:
        csv_reader = csv.DictReader(csv_read)
        for row in tqdm(csv_reader):
            db.voteview_members.update_many(
                {"icpsr": row["icpsr"]},
                {"$set": {"twitter": row["twitter"], "last_updated": datetime.utcnow()}},
                upsert=False
            )

if __name__ == "__main__":
    import_all()
