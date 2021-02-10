import sys
import os
import datetime
import hashlib
import logging
from logging.config import dictConfig

import yaml
import pysftp
from pysftp.helpers import WTCallbacks
import click
import boto3
import botocore

logger = None

def get_logger(logging_config):
    try:
        with open(logging_config) as file:
            config = yaml.load(file)
        dictConfig(config)
    except:
        FORMAT = '[%(asctime)-15s] %(levelname)s [%(name)s] %(message)s'
        logging.basicConfig(format=FORMAT, level=logging.INFO)

    def exception_handler(type, value, tb):
        print("Uncaught exception: {}".format(str(value)), exc_info=(type, value, tb))

    sys.excepthook = exception_handler

    return logging.getLogger('s3_sftp_sync')

def get_config(config_file):
    try:
        with open(config_file) as file:
            config = yaml.load(file)
    except:
        config = {}

    def safe_get(obj, key):
        if key in obj:
            return obj[key]
        return None

    if 's3' not in config:
        config['s3'] = {}

    config['s3']['bucket'] = os.getenv('S3_SFTP_SYNC__S3_BUCKET', safe_get(config['s3'], 'bucket'))
    config['s3']['key_prefix'] = os.getenv('S3_SFTP_SYNC__S3_key_PREFIX', safe_get(config['s3'], 'key_prefix'))

    if 'sftp' not in config:
        config['sftp'] = {}

    config['sftp']['hostname'] = os.getenv('S3_SFTP_SYNC__SFTP_HOSTNAME', safe_get(config['sftp'], 'hostname'))
    config['sftp']['username'] = os.getenv('S3_SFTP_SYNC__SFTP_USERNAME', safe_get(config['sftp'], 'username'))
    config['sftp']['password'] = os.getenv('S3_SFTP_SYNC__SFTP_PASSWORD', safe_get(config['sftp'], 'password'))

    if 'incremental_sync' not in config:
        config['incremental_sync'] = {}

    config['incremental_sync']['last_modified_s3_key'] = os.getenv('S3_SFTP_SYNC__SFTP_LAST_MODIFIED_S3_KEY', safe_get(config['incremental_sync'], 'last_modified_s3_key'))

    return config

def file_md5(file):
    hash_md5 = hashlib.md5()
    while True:
        data = file.read(10240)
        if len(data) == 0:
            break
        hash_md5.update(data)
    file.seek(0)
    return hash_md5.hexdigest()

def s3_md5(s3, bucket, key):
    try:
        response = s3.head_object(
            Bucket=bucket,
            Key=key)
        return response['ETag'].strip('"').strip("'")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] != '404':
            print('Could not fetch S3 object - {}/{}'.format(bucket, key))
            sys.exit(1)

    return None

@click.command()
@click.option('--config-file', default='./config.conf')
@click.option('--logging-config', default='./logging_config.conf')
def main(config_file, logging_config):
    global logger

    logger = get_logger(logging_config)
    config = get_config(config_file)

    print('Starting sync')

    num_files_synced = 0
    num_bytes_synced = 0

    start_time = None
    last_modified = None



    bucket = config['s3']['bucket']
    key_prefix = config['s3']['key_prefix']
    key_id=config['s3']['aws_access_key_id']
    access_key=config['s3']['aws_secret_access_key']

    s3 = boto3.client('s3', aws_access_key_id=key_id, aws_secret_access_key=access_key)

    if 'incremental_sync' in config:
        key = config['incremental_sync']['last_modified_s3_key']
        print('DEBUG', bucket, key)
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            start_time = response['Body'].read().decode('utf-8')
            last_modified = start_time
            print('Using incremental sync with start_time of {} from {}/{}'.format(start_time, bucket, key))
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                print('Could not fetch last modified time S3 object - {}/{}'.format(bucket, key))
                sys.exit(1)

    cnopts = pysftp.CnOpts()
    cnopts.compression = True
    cnopts.hostkeys = None

    with pysftp.Connection(config['sftp']['hostname'],
                           username=config['sftp']['username'],
                           password=config['sftp']['password'],
                           cnopts=cnopts) as sftp:

        print('Walking SFTP server structure')
        wtcb = WTCallbacks()
        # https://pysftp.readthedocs.io/en/release_0.2.8/pysftp.html#pysftp.Connection.walktree
        # 1st arg is the root of the remote directory to descend the cwd
        # 2nd arg is fcallback, "callback  function  to  invoke  for  a  regular  file."
        # 3rd arg is dcallback, "callback  function  to  invoke  for  a  directory."
        # 4th arg is ucallback, " callback function to invoke for an unknown file type."
        # 5th arg is a boolean for recursing (default should be true)
        sftp.walktree('.', wtcb.file_cb, wtcb.dir_cb, wtcb.unk_cb, True)

        for fname in wtcb.flist:
            stats = sftp.sftp_client.stat(fname)

            mtime = str(stats.st_mtime)
            size = stats.st_size
            if start_time == None or mtime >= start_time:
                with sftp.sftp_client.file(fname) as file:
                    if mtime == start_time:
                        s3_hash = s3_md5(s3, bucket, key_prefix + fname)

                        # if s3 object doesn't exist, don't bother hashing sftp file
                        if s3_hash != None:
                            print('{} modified time equals start_time, hash checking file'.format(fname))
                            file_hash = file_md5(file)
                        else:
                            file_hash = None
                    print("if start_time == None or mtime > start_time or s3_hash != file_hash:")
                    print("start_time: '{}', mtime: '{}', s3_hash: '{}', file_hash: '{}'".format(start_time, mtime, s3_hash, file_hash))
                    if start_time == None or mtime > start_time or s3_hash != file_hash:
                        print('Syncing {} - {} mtime - {} bytes'.format(fname, mtime, size))

                        s3.put_object(
                            Bucket=bucket,
                            Key=key_prefix + fname,
                            Body=file,
                            Metadata={
                                'sftp_mtime': mtime,
                                'sftp_sync_time': datetime.datetime.utcnow().isoformat()
                            })

                        num_files_synced += 1
                        num_bytes_synced += size

            if 'incremental_sync' in config and (last_modified == None or mtime >= last_modified):
                last_modified = mtime

        if 'incremental_sync' in config and last_modified != None and last_modified != start_time:
            print('Updating last_modified time {}'.format(last_modified))
            s3.put_object(
                Bucket=bucket,
                Key=config['incremental_sync']['last_modified_s3_key'],
                Body=str(last_modified).encode('utf8'))

        print('Synced {} files and {} bytes'.format(num_files_synced, num_bytes_synced))
