#!/usr/bin/env python

from setuptools import setup

setup(
    name='S3 SFTP Sync',
    version='0.2dev',
    packages=['s3_sftp_sync',],
    description='Syncs files from a SFTP server to an S3 bucket',
    long_description=open('README.md').read(),
    entry_points={
        'console_scripts': [
            's3_sftp_sync=s3_sftp_sync:main',
        ],
    }
)
