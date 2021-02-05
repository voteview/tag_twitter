# tag_twitter

This repository contains the scripts necessary to attach Twitter accounts to congressperson database entries. This is a two step process: the first step pre-populates a list of all verified accounts on Twitter so that verification can be done offline without API access. The second step matches an individual Twitter account to an individual congressperson.

## Setup

Ensure that `config/auth.json` is filled out with valid Twitter API keys.

## Pre-populating verified accounts

The script `populate_verified_users.py` governs this step, which is broken down into two sub-steps: first, receive a list of account IDs that are verified; second, hydrate these users to have human-friendly details. Each of these has a different Twitter timeout, be prepared for this to take several hours.

The script can be run in one of two ways:

* `python populate_verified_users.py --rescan` will run both steps
* `python populate_verified_users.py` will just run the second step, and so is suitable if resuming after a partially completed previous run.

## Matching accounts to individual congressmen

The script `tag_congress.py` governs this step, which requires a user to manually ascertain which Twitter accounts match which users.

Run the script as follows:

* `python tag_congress.py --min_congress 109` will attempt to match Twitter accounts to all congresspersons in the 109th congress and subsequent congresses. If the `--min_congress` argument is not included, the default is 109.

The program will save negative answers (e.g. a user saying the member of congress has no Twitter account) but retain members for whom no candidate accounts were found to begin with. 

At the end of any run of the program, all answers will be saved in `data/archive_results.csv` with the following format:

ICPSR | Name | Congress | Chamber | Twitter
------|------|----------|---------|---------
99913 | BIDEN, Joseph Robinette, Jr. | 117 | President | POTUS
49703 | COLLINS, Susan Margaret | 117 | Senate | SenatorCollins
41903 | SCOTT, Richard Lynn (Rick) | 117 | Senate | SenRickScott
41902 | ROMNEY, Willard Mitt (Mitt) | 117 | Senate | MittRomney
41901 | HAWLEY, Joshua David | 117 | Senate | HawleyMO
21949 | OCASIO-CORTEZ, Alexandria | 117 | House | AOC
21948 | NEGUSE, Joseph | 117 | House | RepJoeNeguse
21946 | MILLER, Carol | 117 | House | RepCarolMiller
21945 | MEUSER, Dan | 117 | House | RepMeuser
99912 | TRUMP, Donald John | 115 | President | 

## Archiving selections

The script `import_archive.py` will load `data/archive_results.csv` and overwrite data in the database. Please note that as with above, members who have been definitively determined to not have Twitter accounts shold be included with the `twitter` column left blank.
