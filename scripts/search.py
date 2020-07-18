#!/usr/bin/env python
# coding: utf-8

# ###### Intro
# - query from twitter api, pipelined to aws RDS
# - before pipelining, check queries for alert, alert sent by email

# establish twitter api connection

# In[ ]:


# import library
import pandas as pd
import numpy as np
import tweepy
import csv
import configparser
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from config import keys, since, fav_count, fwr_count, rt_count
from config import master_bucket, region
from config import account_key_dict, df_account_list
from io import StringIO
import os

import mysql.connector

# email function
import smtplib
from email.message import EmailMessage
import ssl

# read credentials file

# In[ ]:


config = configparser.ConfigParser()
config.read('credentials.cfg')

# establish twitter api connection

# In[ ]:


# tweets' JSON data from twitter API
consumer_key = config['tweepy']['consumer_key']
consumer_secret = config['tweepy']['consumer_secret']
access_token = config['tweepy']['access_token']
access_secret = config['tweepy']['access_secret']

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)

api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

# establish aws rds connection in mysql

# In[ ]:


host = config['mysql_db']['host']
port = config['mysql_db']['port']
user = config['mysql_db']['user']
password = config['mysql_db']['password']
db_name = config['mysql_db']['db_name']
rds = mysql.connector.connect(
    host=host,
    user=user,
    password=password,
    port=port
)
rds.autocommit = True
cursor = rds.cursor()

# *(ignore if not using aws RDS)in aws rds, one default database is created once connected to rds, as set in aws rds previously, the db's name should match with the `db_name` in `credentials.cfg`

# establish aws s3 connection, create bucket and folder to store since_id

# In[ ]:


os.environ['AWS_ACCESS_KEY_ID'] = config['aws']['aws_access_key_id']
os.environ['AWS_SECRET_ACCESS_KEY'] = config['aws']['aws_secret_access_key']

# In[ ]:


s3 = boto3.client('s3', region_name=region)

# In[ ]:


try:
    s3.get_bucket_versioning(Bucket=master_bucket)
except:
    s3.create_bucket(Bucket=master_bucket)
    print('Bucket {} created in region {}'.format(master_bucket, region))

# In[ ]:

try:
    s3.get_object(Bucket=master_bucket, Key='sinceIds/')
except s3.exceptions.NoSuchKey as e:
    s3.put_object(Bucket=master_bucket, Key='sinceIds/')
    print('"sinceIds" folder created')

# alert email function

# * IMPORTANT: when usiing gmail as sender, make sure to turn `Less secure app access` on, as this allows the app to send on Gmail via SMTP
# * Link to turn `Less secure app access` on/off: https://myaccount.google.com/lesssecureapps

# In[ ]:


from_ = config['email']['from_']
to = config['email']['to']
smtp_host = config['email']['smtp_host']
port = config['email']['port']
username = config['email']['username']
password = config['email']['password']

subject = "TC Alert: "


def alert_by_email(subject_, alert_target, alert_msg, test_mode):
    # initialization of database may not send alert
    if test_mode == True:
        return

    alert_text = 'For {}: {}'.format(alert_target, alert_msg)
    msg = EmailMessage()
    msg.set_content(alert_text)
    msg['Subject'] = subject + subject_
    msg['From'] = from_
    msg['To'] = to

    s = smtplib.SMTP('{}:{}'.format(smtp_host, port))
    s.starttls()
    s.login(username, password)
    s.send_message(msg)
    s.quit()


# ### search_hashtag
# query for each key
#  - track output by since_id.csv in s3, create/modify since_id.csv
#  - querry for each key, with pre-setting from search_config.py
#  - output transfer to s3, save new since_id.csv

# create tables for keys

# In[ ]:


print("PART 1")
cursor.execute("USE {}".format(db_name))

# In[ ]:


for key in keys:
    # table with '#' sign has to be surround with ` `
    create_table = """CREATE TABLE IF NOT EXISTS `{}` (
    id int NOT NULL AUTO_INCREMENT,
    user_name varchar(30) NOT NULL,
    tweet varchar(280) NOT NULL,
    followers int NOT NULL,
    likes int NOT NULL,
    retweets int NOT NULL,
    retweeted boolean NOT NULL,
    date datetime NOT NULL,
    PRIMARY KEY (id)
    );""".format(key)

    cursor.execute(create_table)
    print("table {} present in database {}".format(key, db_name))

# get since_id.csv from S3, to avoid duplicate output in query;
# if since_id.csv not initialized, initialization is done in the exception block

# In[ ]:


try:
    since_ids_object = s3.get_object(Bucket=master_bucket, Key='sinceIds/hashtag_sinceid.csv')
    object_body = since_ids_object['Body']
    csv_string = object_body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), )  # the dataframe to store since_ids
    for key in keys:  # append new key to since_id.csv by pd
        if key not in df.key.values:
            df_oneRow = pd.DataFrame([[key, np.NAN]], columns=['key', 'since_id'])
            df = pd.concat([df, df_oneRow])

except s3.exceptions.NoSuchKey as e:
    df = pd.DataFrame(columns=['key', 'since_id'])  # the dataframe to store since_ids
    for key in keys:  # create since_id.csv by pd
        df_oneRow = pd.DataFrame([[key, np.NAN]], columns=['key', 'since_id'])
        df = pd.concat([df, df_oneRow])

df = df.reset_index(drop=True)


# In[ ]:


def keyword_query_sql_string(key):
    return """INSERT INTO `{}`(user_name, tweet, followers, likes, retweets, retweeted, date) VALUES (%s, %s, %s, %s, %s, %s, %s)""".format(
        key)


# In[ ]:


# query by keyword, max timeline possible, many querys are ran at once
def keyword_query_api(key, since, fwr_count, fav_count, rt_count, since_id, api):
    print('Key: {}'.format(key))

    # 1st query
    if since_id == 0:
        tweets = api.search(q=key, lang='en', since=since, count=100, tweet_mode="extended")
    else:
        tweets = api.search(q=key, lang='en', since=since, count=100, since_id=since_id, tweet_mode="extended")

    since_id_list = list()  # temp since_id list per key

    # filter and insert to mysql
    for tweet in tweets:

        since_id_list.append(tweet.id)  # append since_id

        if tweet.user.followers_count >= fwr_count and tweet.favorite_count >= fav_count and tweet.retweet_count >= rt_count:

            sql_row = list()

            if hasattr(tweet, 'retweeted_status'):
                sql_row.extend((tweet.user.screen_name, tweet.retweeted_status.full_text, tweet.user.followers_count,
                                tweet.favorite_count, tweet.retweet_count, 'TRUE', tweet.created_at))

            else:
                sql_row.extend((tweet.user.screen_name, tweet.full_text, tweet.user.followers_count,
                                tweet.favorite_count, tweet.retweet_count, 'FALSE', tweet.created_at))

            sql_insert = keyword_query_sql_string(key)
            cursor.execute(sql_insert, sql_row)

    if tweets:
        max_id = tweets[-1].id - 1
        print('1 query done')
    else:
        # no new queires produced at this run, no update on mysql
        print('No query needed, done')
        return

    # subsequent queries
    while True:

        if since_id == 0:
            tweets = api.search(q=key, lang='en', since=since, count=100, max_id=max_id, tweet_mode="extended")
        else:
            tweets = api.search(q=key, lang='en', since=since, count=100, since_id=since_id, max_id=max_id,
                                tweet_mode="extended")

        # filter and insert to mysql
        for tweet in tweets:

            since_id_list.append(tweet.id)  # append since_id

            if tweet.user.followers_count >= fwr_count and tweet.favorite_count >= fav_count and tweet.retweet_count >= rt_count:

                sql_row = list()

                if hasattr(tweet, 'retweeted_status'):
                    sql_row.extend((
                        tweet.user.screen_name, tweet.retweeted_status.full_text, tweet.user.followers_count,
                        tweet.favorite_count, tweet.retweet_count, 'TRUE', tweet.created_at))
                else:
                    sql_row.extend((tweet.user.screen_name, tweet.full_text, tweet.user.followers_count,
                                    tweet.favorite_count, tweet.retweet_count, 'FALSE', tweet.created_at))

                sql_insert = keyword_query_sql_string(key)
                cursor.execute(sql_insert, sql_row)

        if not tweets:
            df.loc[df.index[df['key'] == key][0], 'since_id'] = max(since_id_list)  # update since_id
            print('done')
            return

        max_id = tweets[-1].id - 1
        print('1 query done')


# In[ ]:


# call the func above, para by key and since_id
print("now search keyword s")
print("there are {} keywords to search from in total".format(len(keys)))
key_count = 1
for key in keys:
    print('now on keyword #{}, {} keywords left'.formart(key_count, len(keys) - key_count))
    if np.isnan(df[df['key'] == key].since_id.values[0]):
        keyword_query_api(key=key, since=since, fwr_count=fwr_count, fav_count=fav_count, rt_count=rt_count, since_id=0,
                          api=api)
    else:
        keyword_query_api(key=key, since=since, fwr_count=fwr_count, fav_count=fav_count, rt_count=rt_count,
                          since_id=df[df['key'] == key].since_id.values[0], api=api)
    key_count += 1

# update since_id to S3, e.g., update tc/sinceIDs/since_id.csv

# In[ ]:


s3.delete_object(Bucket=master_bucket, Key='sinceIds/hashtag_sinceid.csv')  # delete the old since_id.csv
csv_buffer = StringIO()
df.to_csv(csv_buffer, sep=",", index=False)
s3.put_object(Bucket=master_bucket, Key='sinceIds/hashtag_sinceid.csv', Body=csv_buffer.getvalue())

# ## search_account_keyword
# 
# query for each account by key
# 
# - track account by screen_name
# - filter account tweets by since_id
# - update to aws s3

# get since_id.csv from S3, to avoid duplicate output in query

# In[ ]:


print("PART 2")
try:
    since_ids_object = s3.get_object(Bucket=master_bucket, Key='sinceIds/account_keyword_sinceid.csv')
    object_body = since_ids_object['Body']
    csv_string = object_body.read().decode('utf-8')
    df = pd.read_csv(StringIO(csv_string), )  # the dataframe to store since_ids
    for acc in account_key_dict:  # append new key to since_id.csv by pd
        if acc not in df.acc.values:
            df_oneRow = pd.DataFrame([[acc, np.NAN]], columns=['acc', 'since_id'])
            df = pd.concat([df, df_oneRow])

except s3.exceptions.NoSuchKey as e:
    df = pd.DataFrame(columns=['acc', 'since_id'])  # the dataframe to store since_ids
    for acc in account_key_dict:  # create since_id.csv by pd
        df_oneRow = pd.DataFrame([[acc, np.NAN]], columns=['acc', 'since_id'])
        df = pd.concat([df, df_oneRow])
df = df.reset_index(drop=True)

# create table for each twitter account

# In[ ]:


cursor.execute("USE {}".format(db_name))

# check for twitter account validity (i.e. correct account name)

# In[ ]:


print('verifing twitter accounts')
for acc in account_key_dict:
    try:
        api.get_user(screen_name=acc)
    except tweepy.TweepError:
        print('twitter account {} not valid, please check, program will exit immediately.'.format(acc))
        exit(1)
print('all twitter accounts verified')

# In[ ]:


for acc in account_key_dict:
    # table's name with '#' has to be surround with ` `
    create_table = """CREATE TABLE IF NOT EXISTS `{}` (
    id int NOT NULL AUTO_INCREMENT,
    tweet varchar(280) NOT NULL,
    likes int NOT NULL,
    retweets int NOT NULL,
    retweeted boolean NOT NULL,
    date datetime NOT NULL,
    PRIMARY KEY (id)
    );""".format(acc)

    cursor.execute(create_table)
    print("table {} present in database {}".format(acc, db_name))


# In[ ]:


def account_query_sql_string(account):
    return """INSERT INTO `{}`(tweet, likes, retweets, retweeted, date) VALUES (%s, %s, %s, %s, %s)""".format(account)


# In[ ]:


# query by keyword, max timeline possible, many querys are ran at once
def account_query_api(acc, keys, since_id, api):
    print('account: {}'.format(acc))
    print('keys: ', end='')
    print(*keys, sep=', ')

    # 1st query
    if since_id == 0:
        tweets = api.user_timeline(screen_name=acc, count=200, tweet_mode="extended")
    else:
        tweets = api.user_timeline(screen_name=acc, since_id=since_id, count=200, tweet_mode="extended")

    since_id_list = list()  # temp since_id list per key

    # insert into mysql and filter for alert
    for tweet in tweets:

        since_id_list.append(tweet.id)  # append since_id

        # insert into mysql
        sql_row = list()
        if hasattr(tweet, 'retweeted_status'):
            sql_row.extend(
                (tweet.retweeted_status.full_text, tweet.favorite_count, tweet.retweet_count, 'TRUE', tweet.created_at))
            msg = tweet.retweeted_status.full_text
        else:
            sql_row.extend((tweet.full_text, tweet.favorite_count, tweet.retweet_count, 'FALSE', tweet.created_at))
            msg = tweet.full_text
        sql_insert = account_query_sql_string(acc)
        cursor.execute(sql_insert, sql_row)

        # filter for alert
        tweet_lowercase = tweet.full_text.lower()
        key_found = list()
        for key in keys:
            if key in tweet_lowercase:
                key_found.append(key)

        # send email alert if key in account found   
        if key_found:
            print("sending email...")

            # get coin name as part of email subject
            account_row = df_account_list.loc[df_account_list[df_account_list.columns[1]] == acc]
            subject_ = account_row.iloc[0][0]

            alert_by_email(subject_=subject_, alert_target='@' + acc, alert_msg=msg, test_mode=False)

    if tweets:
        max_id = tweets[-1].id - 1
        print('1 query done')
    else:
        # no new queires produced at this run, no update on mysql
        print('No query needed, done')
        return

    # subsequent queries
    while True:

        if since_id == 0:
            tweets = api.user_timeline(screen_name=acc, count=200, max_id=max_id, tweet_mode="extended")
        else:
            tweets = api.user_timeline(screen_name=acc, since_id=since_id, count=200, max_id=max_id,
                                       tweet_mode="extended")

        # insert into mysql and filter for alert
        for tweet in tweets:

            since_id_list.append(tweet.id)  # append since_id

            # insert into mysql
            sql_row = list()
            if hasattr(tweet, 'retweeted_status'):
                sql_row.extend((tweet.retweeted_status.full_text, tweet.favorite_count, tweet.retweet_count, 'TRUE',
                                tweet.created_at))
                msg = tweet.retweeted_status.full_text
            else:
                sql_row.extend((tweet.full_text, tweet.favorite_count, tweet.retweet_count, 'FALSE', tweet.created_at))
                msg = tweet.full_text
            sql_insert = account_query_sql_string(acc)
            cursor.execute(sql_insert, sql_row)

            # filter for alert
            tweet_lowercase = tweet.full_text.lower()
            key_found = list()
            for key in keys:
                if key in tweet_lowercase:
                    key_found.append(key)

            # send email alert if key in account found   
            if key_found:
                print("sending email...")

                # get coin name as part of email subject
                account_row = df_account_list.loc[df_account_list[df_account_list.columns[1]] == acc]
                subject_ = account_row.iloc[0][0]

                alert_by_email(subject_=subject_, alert_target='@' + acc, alert_msg=msg, test_mode=False)

        if not tweets:
            df.loc[df.index[df['acc'] == acc][0], 'since_id'] = max(since_id_list)  # update since_id
            print('done')
            return

        max_id = tweets[-1].id - 1
        print('1 query done')


# In[ ]:


# call the func above, para by key and since_id
print("now search keyword in accounts")
print("there are {} accounts to search from in total".format(len(account_key_dict)))
acc_count = 1
for acc in account_key_dict:
    print('now on account #{}, {} accounts left'.format(acc_count, len(account_key_dict) - acc_count))
    if np.isnan(df[df['acc'] == acc].since_id.values[0]):
        account_query_api(acc=acc, keys=account_key_dict[acc], since_id=0, api=api)
    else:
        account_query_api(acc=acc, keys=account_key_dict[acc], since_id=df[df['acc'] == acc].since_id.values[0],
                          api=api)
    acc_count += 1

# In[ ]:


# update since_id to S3, tc/sinceIDs/since_id.csv
s3.delete_object(Bucket=master_bucket, Key='sinceIds/account_keyword_sinceid.csv')  # delete the old since_id.csv
csv_buffer = StringIO()
df.to_csv(csv_buffer, sep=",", index=False)
s3.put_object(Bucket=master_bucket, Key='sinceIds/account_keyword_sinceid.csv', Body=csv_buffer.getvalue())

# In[ ]:


cursor.close()
rds.close()
print('Program finished')
