""" Helper to perform non-US removal step. """

import io
import sqlite3
from tqdm import tqdm


def do_it():
    """ Performs the non-US removal step from populate_verified_users. """
    conn = sqlite3.connect("../data/verified_users")
    db = conn.cursor()

    non_us_locations = (
        [unicode(x.strip()) for x in
         io.open("../config/non_us_locations.txt", "r", encoding="utf-8").readlines()
         if x.strip()])

    for location in non_us_locations:
        print(location)
        db.execute("DELETE FROM twitter_users WHERE location=?;", (location,))
    conn.commit()

    db.execute("VACUUM")
    conn.commit()


if __name__ == "__main__":
    do_it()
