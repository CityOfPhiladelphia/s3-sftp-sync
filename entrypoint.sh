#!/bin/bash
echo "here"
echo $SFTP_HOSTNAME
sed -i -e "s/<sfpt-hostname>/$SFTP_HOSTNAME/g" -e "s/<sfpt-username>/$SFTP_USERNAME/g" -e "s/<sfpt-password>/$SFTP_PASSWORD/g" -e "s/<s3-key>/$S3_KEY/g" -e "s/<s3-bucket>/$S3_BUCKET/g" config.yml
cat config.yml
s3_sftp_sync --config-file config.yml
