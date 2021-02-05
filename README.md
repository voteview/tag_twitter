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

TBA
