import configparser
import mysql.connector
import boto3
from config import master_bucket, region


# this script will reset the mysql database TC, and delete the bucket in S3

print('resetting mysql database')

# db connection
config = configparser.ConfigParser()
config.read('credentials.cfg')
host = config['mysql_db']['host']
port = config['mysql_db']['port']
user = config['mysql_db']['user']
password = config['mysql_db']['password']
db_name = config['mysql_db']['db_name']

rds = mysql.connector.connect(
    host=host,
    user=user,
    password=password,
    port = port
)
rds.autocommit = True
cursor = rds.cursor()

print('resetting mysql database done')

# reset database
drop_TC = "DROP DATABASE IF EXISTS {}".format(db_name)
create_TC = "CREATE DATABASE IF NOT EXISTS {}".format(db_name)
cursor.execute(drop_TC)
cursor.execute(create_TC)
cursor.close()
rds.close()


print('cleaning S3 bucket')

# aws s3 connection
s3 = boto3.resource('s3')
bucket = s3.Bucket(master_bucket)
bucket.objects.all().delete()

print('cleaning S3 bucket done')

print('reset finished')

