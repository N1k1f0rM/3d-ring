#!/usr/bin/env python3

import json
import logging
import os
import sys

import boto3
from botocore.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


endpoint = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
bucket = "data"


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        use_ssl=False,
        verify=False,
    )


def list_object_folders(prefix=""):
    s3 = get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    uids = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for comm in page.get("CommonPrefixes", []):
            folder = comm["Prefix"].rstrip("/")
            uid = folder.split("/")[-1]
            uids.add(uid)
    return sorted(uids)


def upload_json_to_minio(local_path, s3_key):
    s3 = get_s3_client()
    s3.upload_file(local_path, bucket, s3_key)
    logger.info(f"Uploaded {local_path} to s3://{bucket}/{s3_key}")


def main():
    logger.info("Fetching UID list from MinIO bucket data")
    uids = list_object_folders()
    if not uids:
        logger.error("No UID folders found in bucket data")
        sys.exit(1)

    logger.info(f"Found {len(uids)} UIDs: {uids[:5]}...")

    split_idx = int(len(uids) * 0.9)
    train_uids = uids[:split_idx]
    val_uids = uids[split_idx:]

    local_data_root = "/opt/airflow/project/data/clear"
    os.makedirs(local_data_root, exist_ok=True)
    train_json_local = os.path.join(local_data_root, "train.json")
    val_json_local = os.path.join(local_data_root, "val.json")

    with open(train_json_local, "w") as f:
        json.dump(train_uids, f)
    with open(val_json_local, "w") as f:
        json.dump(val_uids, f)

    logger.info(f"Saved train.json and val.json to {local_data_root}")

    upload_json_to_minio(train_json_local, "metadata/train.json")
    upload_json_to_minio(val_json_local, "metadata/val.json")

    logger.info("JSON generation and upload completed successfully.")


if __name__ == "__main__":
    main()
