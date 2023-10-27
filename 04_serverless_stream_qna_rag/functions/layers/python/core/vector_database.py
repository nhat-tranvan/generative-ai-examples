import json
from typing import Dict, List, Optional
from uuid import uuid4
import os
from langchain.embeddings import SagemakerEndpointEmbeddings
from langchain.embeddings.sagemaker_endpoint import EmbeddingsContentHandler
from langchain.vectorstores import OpenSearchVectorSearch
from opensearchpy import OpenSearch, RequestsHttpConnection
from botocore.session import Session
from requests_aws4auth import AWS4Auth
from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter


class ContentHandler(EmbeddingsContentHandler):
    content_type = "application/json"
    accepts = "application/json"

    def transform_input(self, inputs: list[str], model_kwargs: Dict) -> bytes:
        input_str = json.dumps({"text_inputs": inputs, **model_kwargs})
        return input_str.encode("utf-8")

    def transform_output(self, output: bytes) -> List[List[float]]:
        response_json = json.loads(output.read().decode("utf-8"))
        return response_json["embedding"]


class VectorDatabase:
    def __init__(self, opensearch_url: str, opensearch_user: Optional[str], opensearch_pass: Optional[str], opensearch_index: str, env: str) -> None:
        self.opensearch_url = opensearch_url
        self.opensearch_user = opensearch_user
        self.opensearch_pass = opensearch_pass
        self.opensearch_index = opensearch_index

        content_handler = ContentHandler()
        self.embeddings = SagemakerEndpointEmbeddings(
            endpoint_name=os.environ.get('SM_ENDPOINT_NAME'),
            region_name=os.environ.get('SM_ENDPOINT_REGION'),
            content_handler=content_handler
        )

        self.docsearch = OpenSearchVectorSearch(
            index_name=opensearch_index,
            embedding_function=self.embeddings,
            opensearch_url=opensearch_url,
            http_auth=self._get_auth(env, opensearch_user, opensearch_pass),
            timeout=300,
            use_ssl=False if env == 'local' else True,
            verify_certs=False if env == 'local' else True,
            connection_class=RequestsHttpConnection,
        )

    def _get_auth(self, env, username, password):
        if env == 'local':
            return (username, password)

        service = 'aoss'  # must set the service as 'aoss'
        region = 'ap-southeast-1'
        session = Session()
        credentials = session.get_credentials()
        awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service,
                           session_token=credentials.token)

        return awsauth

    def get_retreiver(self) -> OpenSearchVectorSearch:
        return self.docsearch

    def insert_documents(self, documents):
        response = self.docsearch.add_documents(documents)

        return response

    def similarity_search(self, query: str, k: int = 1):
        docs = self.docsearch.similarity_search(
            query,
            k=k,
            search_type="script_scoring"
        )

        return docs

    def _load_documents(self, file_path: str):
        loader = TextLoader(file_path)
        documents = loader.load()
        text_splitter = CharacterTextSplitter(chunk_size=1000,
                                              chunk_overlap=0)
        docs = text_splitter.split_documents(documents)

        print('total churns: {}'.format(len(docs)))

        return docs
    

    def ingest_pipeline(self, file_path: str):
        docs = self._load_documents(file_path)
        
        chunks = self.divide_chunks(docs, 10)

        for chunk in chunks:
            response = self.insert_documents(chunk)
    
    def divide_chunks(self, docs, n):
        # looping till length l
        for i in range(0, len(docs), n): 
            yield docs[i:i + n]
