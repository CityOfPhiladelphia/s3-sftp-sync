#!/usr/bin/env python3

import sys
import configparser
import datetime
import hashlib
import logging
from logging.config import fileConfig

import pysftp
from pysftp.helpers import WTCallbacks
import click
import boto3
import botocore

logger = None

def get_logger(logging_config):
    try:
        fileConfig(logging_config)
    except:
        FORMAT = '[%(asctime)-15s] %(levelname)s [%(name)s] %(message)s'
        logging.basicConfig(format=FORMAT, level=logging.INFO)

    def exception_handler(type, value, tb):
        logger.exception("Uncaught exception: {}".format(str(value)), exc_info=(type, value, tb))

    sys.excepthook = exception_handler

    return logging.getLogger('s3_sftp_sync')

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
            logger.exception('Could not fetch S3 object - {}/{}'.format(bucket, key))
            sys.exit(1)

    return None

@click.command()
@click.option('--config-file', default='config.conf')
@click.option('--logging-config', default='logging_config.conf')
def main(config_file, logging_config):
    global logger

    logger = get_logger(logging_config)

    logger.info('Starting sync')

    config = configparser.ConfigParser()
    config.read(config_file)

    num_files_synced = 0
    num_bytes_synced = 0

    start_time = None
    last_modified = None

    s3 = boto3.client('s3',
                      aws_access_key_id=config['s3']['aws_access_key_id'],
                      aws_secret_access_key=config['s3']['aws_secret_access_key'])
    bucket = config['s3']['bucket']
    key_prefix = config['s3']['key_prefix']

    if 'incremental_sync' in config:
        key = config['incremental_sync']['last_modified_s3_key']
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            start_time = response['Body'].read().decode('utf-8')
            last_modified = start_time
            logger.info('Using incremental sync with start_time of {} from {}/{}'.format(start_time, bucket, key))
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                logger.exception('Could not fetch last modified time S3 object - {}/{}'.format(bucket, key))
                sys.exit(1)

    cnopts = pysftp.CnOpts()
    cnopts.compression = True

    if 'verify_host_key' in config['sftp'] and config['sftp']['verify_host_key'].lower() == 'false':
        cnopts.hostkeys = None

    with pysftp.Connection(config['sftp']['hostname'],
                           username=config['sftp']['username'],
                           password=config['sftp']['password'],
                           cnopts=cnopts) as sftp:

        logger.info('Walking SFTP server structure')
        wtcb = WTCallbacks()
        sftp.walktree('/', wtcb.file_cb, wtcb.dir_cb, wtcb.unk_cb)

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
                            logger.info('{} modified time equals start_time, hash checking file'.format(fname))
                            file_hash = file_md5(file)
                        else:
                            file_hash = None

                    if start_time == None or mtime > start_time or s3_hash != file_hash:
                        logger.info('Syncing {} - {} mtime - {} bytes'.format(fname, mtime, size))

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
            logger.info('Updating last_modified time {}'.format(last_modified))
            s3.put_object(
                Bucket=bucket,
                Key=config['incremental_sync']['last_modified_s3_key'],
                Body=str(last_modified).encode('utf8'))

        logger.info('Synced {} files and {} bytes'.format(num_files_synced, num_bytes_synced))

if __name__ == '__main__':
        main()
