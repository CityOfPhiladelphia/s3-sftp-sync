# S3 SFTP Sync

Syncs files from a SFTP server to an S3 bucket.

### Usage:

```sh
./s3_sftp_sync.py
```

```sh
./s3_sftp_sync.py --config-file /path/to/config.conf
```

```sh
./s3_sftp_sync.py --logging-file /path/to/logging_config.conf
```

```sh
./s3_sftp_sync.py --config-file /path/to/config.conf --logging-file /path/to/logging_config.conf
```

### Configuration File

```
[sftp]
hostname = secure-ftp.phila.gov ## SFTP server host or IP
username = Opaproperty ## SFTP username
password = foo ## SFTP password
verify_host_key = false ## Wether to verify the SFTP host, set to true if possible

[s3]
bucket = phl-data-dropbox ## bucket to place SFTP data
key_prefix = sftp ## key prefix for S3 destination files eg /sftp/original/file/path
aws_access_key_id = foo ## an AWS access key ID. Omit of you would like to use insstance role or ~/.aws
aws_secret_access_key = bar ## an AWS access key secret. Omit of you would like to use insstance role or ~/.aws

[incremental_sync] ## remove this section to use full sync
last_modified_s3_key = sftp-sync-last-modified ## Key used for incremental sync
```

### Logging Configuration File

Standard python logging file in ini format.