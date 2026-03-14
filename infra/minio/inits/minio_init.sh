#!/bin/bash

set -e

MINIO_ROOT_USER=$1
MINIO_ROOT_PASSWORD=$2

until mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} 2>/dev/null;
do
    echo "Wait..."
    sleep 3
done


echo "Creating buckets"

for bucket in data models mlflow-bucket sd-res ben2 hunyuan; do
    if mc ls local/${bucket} 2>/dev/null; then
        echo "Already exists ${bucket}"
    else
        mc mb local/${bucket} --region=ru-1
        echo "Create ${bucket}"
    fi
done
