# S3 SFTP Sync

Syncs files from a SFTP server to an S3 bucket.

### Install:

```sh
pip install git+https://github.com/CityOfPhiladelphia/s3-sftp-sync.git
```

### Usage:

```sh
s3_sftp_sync
```

```sh
s3_sftp_sync --config-file /path/to/config.conf
```

```sh
s3_sftp_sync --logging-file /path/to/logging_config.conf
```

```sh
s3_sftp_sync --config-file /path/to/config.conf --logging-file /path/to/logging_config.conf
```

### Configuration File

```
sftp:
  hostname: secure-ftp.phila.gov ## SFTP server host or IP
  username: Opaproperty ## SFTP username
  password: password ## SFTP password
  verify_host_key: false ## Wether to verify the SFTP host, set to true if possible
s3:
  bucket: opa-sftp-backup ## bucket to place SFTP data in
  key_prefix: sftp ## key prefix for S3 destination files eg /sftp/original/file/path
  aws_access_key_id: SOMEKEYID ## an AWS access ke id. Omi if you would like to use instance role or ~/.aws
  aws_secret_access_key: SOMEKEY ## an AWS access key secret. Omit of you would like to use insstance role or ~/.aws
incremental_sync:
  last_modified_s3_key: sftp-sync-last-modified ## Key used for incremental sync
```

### Logging Configuration File

Standard python logging file in ini format.
