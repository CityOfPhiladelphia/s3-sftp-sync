FROM python:3.8
COPY . /app
WORKDIR /app


RUN pip install -r requirements.txt

RUN python setup.py bdist_wheel

RUN python -m pip install dist/S3_SFTP_Sync-0.2.dev0-py3-none-any.whl

#CMD [ "s3_sftp_sync","--config-file", "logging_config.conf" ]
ENTRYPOINT ["s3_sftp_sync"]