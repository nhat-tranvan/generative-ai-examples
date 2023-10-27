from core.vector_database import VectorDatabase
import os
import boto3

ENV = os.environ.get("ENV", "local")
OPENSEARCH_URL = os.environ.get('OPENSEARCH_URL', "https://localhost:9200")
OPENSEARCH_USER = os.environ.get("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD", "admin")
OPENSEARCH_INDEX_NAME = os.environ.get(
    "OPENSEARCH_INDEX_NAME", "index-document-vector-tenant-02")

s3_client = boto3.client('s3')


def handler(event, context):
    print('--- Starting ---')
    # Get our bucket and file name
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    print('Source file: {}/{}'.format(bucket, key))

    file_path = '/tmp/{}'.format(key)

    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))

    # Get our object
    s3_client.download_file(bucket, key, file_path)

    # file_path = 'data/state_of_the_union_03.txt'
    print('Downloaded document to: {}'.format(file_path))

    vector_db = VectorDatabase(
        OPENSEARCH_URL, OPENSEARCH_USER, OPENSEARCH_PASSWORD, OPENSEARCH_INDEX_NAME, ENV)

    vector_db.ingest_pipeline(file_path)

    print('--- End ---')
    return file_path