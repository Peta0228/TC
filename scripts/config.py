import pandas as pd

# part 1: key(hashtag) search
try:
    df_key_list = pd.read_csv('../search_settings/key_list.csv')
except FileNotFoundError:
    print('can not locate "../search_settings/key_list.csv", please check if "key_list.csv" is in the correct directory')
    exit(1)

# VARS TO IMPORT
keys = df_key_list[df_key_list.columns[0]].tolist()
since = '2020-06-01'  # starting date of search result to return
fwr_count = 1000  # follower_count >=, any int
fav_count = 0  # favorite_count >=, any int
rt_count = 0  # retweet_count >=, any int

# part 2: account-keyword search
try:
    df_account_key_list = pd.read_csv('../search_settings/account_key_list.csv')
except:
    print(
        'can not locate "../search_settings/account_key_list.csv", please check if "account_list_key.csv" is in the correct directory')
    exit(1)

try:
    # VARS TO IMORT
    df_account_list = pd.read_csv('../search_settings/account_list.csv')
except:
    print(
        'can not locate "./search_settings/account_list.csv", please check if "account_list_csv" is in the correct directory')
    exit(1)

# create account-key pair into a dictionary
account_list = df_account_list[df_account_list.columns[1]].tolist()
temp_dict = dict()
for acc in account_list:
    temp_dict[acc] = df_account_key_list[df_account_key_list.columns[0]].tolist()

# VARS TO IMPORT
account_key_dict = temp_dict # account-ket pairs

# VARS TO IMPORT, aws S3 details
master_bucket = ''  # name of output bucket, avoid global bucket name duplication in aws S3
region = 'us-east-1'  # region of output bucket
