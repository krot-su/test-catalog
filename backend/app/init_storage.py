"""One-shot MinIO setup: bucket with public object reads and a bucket-scoped user for the API."""
import json
import logging
import os
import tempfile
import time

from minio import Minio
from minio.credentials import StaticProvider
from minio.minioadmin import MinioAdmin

log = logging.getLogger(__name__)

API_POLICY_NAME = "catalog-api"


def public_read_policy(bucket: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            }
        ],
    }


def api_user_policy(bucket: str) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{bucket}"],
            },
        ],
    }


def wait_for_minio(client: Minio, timeout_sec: int = 90) -> None:
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            client.list_buckets()
            return
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    endpoint = os.environ["S3_ENDPOINT"]
    bucket = os.environ.get("S3_BUCKET", "products")
    root_user = os.environ["MINIO_ROOT_USER"]
    root_password = os.environ["MINIO_ROOT_PASSWORD"]
    api_access_key = os.environ["S3_ACCESS_KEY"]
    api_secret_key = os.environ["S3_SECRET_KEY"]

    client = Minio(endpoint, access_key=root_user, secret_key=root_password, secure=False)
    wait_for_minio(client)

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.set_bucket_policy(bucket, json.dumps(public_read_policy(bucket)))

    admin = MinioAdmin(endpoint, credentials=StaticProvider(root_user, root_password), secure=False)
    admin.user_add(api_access_key, api_secret_key)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as policy_file:
        json.dump(api_user_policy(bucket), policy_file)
    try:
        admin.policy_add(API_POLICY_NAME, policy_file.name)
    finally:
        os.remove(policy_file.name)
    admin.policy_set(API_POLICY_NAME, user=api_access_key)
    log.info("Bucket %s and API user %s are ready", bucket, api_access_key)


if __name__ == "__main__":
    main()
