#!/usr/bin/env python3

import configparser
import datetime
import hashlib

import pysftp
from pysftp.helpers import WTCallbacks
import click
import boto3
import botocore

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
            raise e

    return None

@click.command()
@click.option('-c','--config-file', default='config.conf')
def main(config_file):
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
        try:
            response = s3.get_object(Bucket=bucket, Key=config['incremental_sync']['last_modified_s3_key'])
            start_time = response['Body'].read().decode('utf-8')
            last_modified = start_time
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                raise e

    cnopts = pysftp.CnOpts()

    if 'verify_host_key' in config['sftp'] and config['sftp']['verify_host_key'].lower() == 'false':
        cnopts.hostkeys = None

    with pysftp.Connection(config['sftp']['hostname'],
                           username=config['sftp']['username'],
                           password=config['sftp']['password'],
                           cnopts=cnopts) as sftp:
        wtcb = WTCallbacks()
        sftp.walktree('/', wtcb.file_cb, wtcb.dir_cb, wtcb.unk_cb)

        for fname in wtcb.flist:
            print(fname)
            stats = sftp.sftp_client.stat(fname)

            mtime = str(stats.st_mtime)

            print(mtime)
            print(start_time)

            if start_time == None or mtime >= start_time:
                file = sftp.sftp_client.file(fname)

                s3_hash = s3_md5(s3, bucket, key_prefix + fname)

                if s3_hash != None:
                    print('hashing sftp file')
                    file_hash = file_md5(file)
                    print('done hashing sftp file')

                print(s3_hash)
                print(type(s3_hash))
                print(file_hash)
                print(type(file_hash))
                print(s3_hash == file_hash)

                if s3_hash == None or s3_hash != file_hash:
                    print('Syncing {}'.format(fname))

                    s3.put_object(
                        Bucket=bucket,
                        Key=key_prefix + fname,
                        Body=file,
                        Metadata={
                            'sftp_mtime': mtime,
                            'sftp_sync_time': datetime.datetime.utcnow().isoformat()
                        })

                    num_files_synced += 1
                    num_bytes_synced += stats.st_size

            if 'incremental_sync' in config and (last_modified == None or mtime >= last_modified):
                last_modified = mtime

        if 'incremental_sync' in config and last_modified != None:
            s3.put_object(
                Bucket=bucket,
                Key=config['incremental_sync']['last_modified_s3_key'],
                Body=str(last_modified).encode('utf8'))

        print('Synced {} files and {} bytes'.format(num_files_synced, num_bytes_synced))

if __name__ == '__main__':
    main()
