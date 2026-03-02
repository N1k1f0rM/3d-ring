import os
import sys
import argparse
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


load_dotenv()

def create_s3_client():
    end = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://localhost:9000")
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

    if not access_key or not secret_key:
        raise ValueError("No credintials")
    
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url=end,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        use_ssl=False,  # для локального MinIO без HTTPS
        verify=False    # если самоподписанный сертификат
    )
    return s3