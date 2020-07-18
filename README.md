# Twitter Crawler with MySql

## Introduction

The applicaiton can either serarch directly in twiiter(like the search bar in twitter); or search by accounts, and looking for specific keywords in tweets of the accounts found.

The script has strong reusablity, the application is able to query from twitter overtime, it is designed as an autorun process in system background.

## Search by keyword -- PART 1

 - search by keyword in twitter; e.g., keyword: #CCT, ABBC, cat.
 - the search behaves just like the search bar in twitter, returning tweets containing the keyword in reverse-chronological order (from newest to oldest)
 - if a tweet is a retweet, only the orginal tweet's text will be used (as the original tweet deemed to be more informative in general in search result) as the search result
 - filter the search results by three conditons: followers count of the tweet's account, favorite count of the tweet, and retweets count.
 - push each keyword's search results into a separate database, 

## Search by account-keyword -- PART 2

- search by account-keyword pair in twitter; e.g., account: @cat_flurry, @funky_dog, keyword: apple, clever
- for a list of accounts, search their tweets and looking for tweets containing  any of the keywords specified.
- push each account's tweets into a separate database, send email alerts for tweets containing keywords 

## Data format in database

Each table in database is either the result of a key in PART 1, or a account in PART 2.

Each row in table represents a tweet in search result.

For PART 1, {id, user_name, tweet, followers, likes, retweets, retweeted, date}
- id: primary key of table
- user_name: tweet's account name
- tweet: content of tweet
- followers: account's follower
- likes: tweet's likes (favorites)
- retweets: tweet's retweets
- retweeted: whether the tweet is a retweet
- date: timestamp of tweet 


For PART 2, {id, tweet, likes, retweets, retweeted, date}
- id: primary key of table
- tweet: content of tweet
- likes: tweet's likes (favorites)
- retweets: tweet's retweets
- retweeted: whether the tweet is a retweet
- date: timestamp of tweet 

## Prerequisites

Before running, ensure the following requirements are met in the system:

-  Python 3
- Python libraryies: pandas, numpy, tweepy, boto3, mysql.connector
- a MySql database connection,whether locally/remote
- an aws account, with an access Id/key pair; the access Id should have S3 access(if using aws RDS to create MySql db, should have RDS access as well) in aws IAM
- an email account with smtp host and port known, (e.g., gmail: smtp_host = smtp.gmail.com, port = 587)

## File explanations

- **TC.py**: main .py file to run the program, it automates the running of applicaiton, (by default every 10 mins); feel free to change the inteval of auto running, by changing the count var
- **scripts/serch.py**: contain the logic and main execution of the program
- **scripts/config.py**: collect search settings for  **scripts/serch.py** to use
- **scripts/credentials.cfg**: contain the credentials of twitter developer accounts, MySql db conneciton, and email account
- **reset_scheme.py**: reset the db in MySql db, and clear the aws S3 bucket used for log data; DO NOT RUN this unless you want to start all over, as this clears all query results in db
- **search_settings/key_list.csv**: used for PART 1, input in `key` column to be searched in twitter
- **search_settings/account_list.csv**: used for PART 2, input in `CoinName` column  is an alias for input in the same row of `Twitter` column, the program will only search for accounts  in `Twitter` column, but will send email with a title in the corresponding `CoinName` field. 
- **search_settings/account_key_list.csv**: used for PART 2, inputs in `key-lowercase-required` are keywords to look for in each account's tweets; any one key found in the tweet will result an alert   

## How to install/configure

*  directroy/path format  varies in Windows and Linux, the following is only going to provide directions that are sufficient for Linux/MacOS; if using Windows, please also check session `How to configure for windows` below

1. in **scripts/credentials.cfg**, make sure to fill in the following:
    - [aws]: aws access Id/key credentials
    - [tweepy]: a twitter developer account will provide the secret keys you need, [register here](https://developer.twitter.com/apps)
    - [mysql_db]: a MySql database connection, recommend using an aws RDS MySql database, but any MySql db connection is okay
    - [email]: a email account wiht smtp host, recommend using gmail; if using gmail, please also check session `IMPORTANT NOTES` below

2. in **scripts/config.py**, fill in the following:
    -  in line 12 - 15, fill in the vars required for PART 1, PART 1 only push tweets satisfy `fwr_count`, `fav_count`, and `rt_count` into database
    - in line 43, fill in the var required for log data, this var should be the name of a bucket in aws S3, you have to _avoid global bucket name duplication in aws S3_, so give it a complex name and check in aws S3 first to make sure the name is unique globally
    - in line 44, change the var if you want aws service in the program to run in another region, but usually `us-east-1` is good enough

3. in **search_settings/key_list.csv**: fill the 1st column with keywords you would like to search in PART 1

4. in **search_settings/account_list.csv**: fill the 2nd column with twitter account you woule like to search in PART 2, fill in the 1st column with the alias of 2nd column's corresponding field, which will be used as the title of email alert

5. in **search_settings/account_key_list.csv**: fill the 1st column with keys to look for in accoutns in PART 2, entries should be lowercase

## How to configure for windows

* Before proceeding, make sure all steps in `How to install/configure` are done

1. in **scripts/config.py**:
    - in line 5,19, 27, change vars into Windows style file path

2. in **scripts/search.py**:
    - in line 41, change parameter into Windows style file path

## How to run

Finally!

In CLI/Terminal, navigate to the directory of  **TC.py**, run the command: `$ python3 TC.py ./scripts/search.py`.

Note that the path to **scripts/search.py** is different in Windows.

The program should produce outputs every 10mins.

If you would like to exit, type `Ctrl +Z` , but please only do so when the program finishes the last auto run

If errors, check program outputs.

## IMPORTANT NOTES

- during the first run in the autorun process, the application needs to quey all historical tweets containing keywords which are dated from the `since` para specified in **config.py** in PART 1, and all histroical tweets from the accounts in PART 2; this may result a very long 1st run depending on the number of keywords and accounts specified in each part; but this first run initialization is necessary for future runs' consistency 

- when using Gmail as smtp server, make sure to turn `Less secure app access` on, as this allows the app to use Gmai's SMTP host; [turn on here](https://myaccount.google.com/lesssecureapps)

