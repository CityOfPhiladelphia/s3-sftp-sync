#!/usr/bin/env python

from distutils.core import setup

setup(
    name='S3 SFTP Sync',
    version='0.1dev',
    packages=['s3_sftp_sync',],
    description='Syncs files from a SFTP server to an S3 bucket',
    long_description=open('README.md').read(),
    install_requires=[
        'boto3==1.4.4',
        'click==6.7',
        'PyYAML==3.12',
        'pysftp==0.2.9'
    ],
    entry_points={
        'console_scripts': [
            's3_sftp_sync=s3_sftp_sync:main',
        ],
    }
)
