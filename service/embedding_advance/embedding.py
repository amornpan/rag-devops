#!/usr/bin/env python
# coding: utf-8
import os
import torch
import nest_asyncio
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.vector_stores.opensearch import OpensearchVectorStore, OpensearchVectorClient
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import pickle
from pathlib import Path
import pypdf
from opensearchpy import OpenSearch, ConnectionError
import logging
import time
from urllib3.exceptions import NewConnectionError
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Apply nest_asyncio to avoid runtime errors
nest_asyncio.apply()

# OpenSearch configuration
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", "http://opensearch:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "webinar_pdf_index")
TEXT_FIELD = "content"
EMBEDDING_FIELD = "embedding"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
MODEL_NAME = 'BAAI/bge-m3'
VECTOR_DIM = 1024

def wait_for_opensearch(timeout=300):
    """Wait for OpenSearch to be ready"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(OPENSEARCH_ENDPOINT)
            if response.status_code == 200:
                logger.info("OpenSearch is ready")
                return True
        except:
            logger.info("Waiting for OpenSearch...")
            time.sleep(5)
    raise TimeoutError("OpenSearch did not become ready in time")

def setup_opensearch(max_retries=5):
    """Setup OpenSearch client and ensure index exists"""
    host = OPENSEARCH_ENDPOINT.split('://')[1].split(':')[0]
    port = int(OPENSEARCH_ENDPOINT.split(':')[-1])
    
    # Wait for OpenSearch to be ready
    wait_for_opensearch()
    
    # Setup client with retries
    for attempt in range(max_retries):
        try:
            client = OpenSearch(
                hosts=[{'host': host, 'port': port}],
                http_compress=True,
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False,
                retry_on_timeout=True,
                max_retries=3
            )
            
            # Check if index exists
            if not client.indices.exists(OPENSEARCH_INDEX):
                mapping = {
                    "mappings": {
                        "properties": {
                            EMBEDDING_FIELD: {
                                "type": "knn_vector",
                                "dimension": VECTOR_DIM,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "nmslib"
                                }
                            },
                            TEXT_FIELD: {
                                "type": "text"
                            },
                            "metadata": {
                                "type": "object"
                            }
                        }
                    }
                }
                client.indices.create(index=OPENSEARCH_INDEX, body=mapping)
                logger.info(f"Created index {OPENSEARCH_INDEX}")
            return client
            
        except (ConnectionError, NewConnectionError) as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Connection attempt {attempt + 1} failed, retrying...")
            time.sleep(5)

def read_pdf(file_path):
    """Read PDF file and return Document object"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return Document(text=text, metadata={"file_path": str(file_path)})
    except Exception as e:
        logger.error(f"Error reading PDF {file_path}: {str(e)}")
        raise

def process_documents():
    """Process all PDF documents in the corpus directory"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")
    
    # Setup PDF directory
    pdf_dir = Path("pdf_corpus")
    if not pdf_dir.exists():
        os.makedirs("pdf_corpus")
        logger.info("Created pdf_corpus directory")
    
    # Read documents
    documents = []
    for pdf_file in pdf_dir.glob("**/*.pdf"):
        logger.info(f"Processing: {pdf_file}")
        try:
            doc = read_pdf(pdf_file)
            documents.append(doc)
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {str(e)}")
            continue
    
    logger.info(f"Loaded {len(documents)} documents")
    return documents

def create_index(documents):
    """Create vector store index from documents"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Create nodes
    splitter = TokenTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separator=" ")
    nodes = splitter.get_nodes_from_documents(documents, show_progress=True)
    logger.info(f"Created {len(nodes)} nodes")
    
    # Setup embedding model
    embed_model = HuggingFaceEmbedding(
        model_name=MODEL_NAME,
        max_length=CHUNK_SIZE,
        device=device
    )
    
    # Get embedding dimension
    embeddings = embed_model.get_text_embedding("test")
    dim = len(embeddings)
    if dim != VECTOR_DIM:
        raise ValueError(f"Model produces {dim}-dimensional vectors, but index expects {VECTOR_DIM} dimensions")
    logger.info(f"Embedding dimension: {dim}")
    
    # Setup OpensearchVectorClient with retries
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    session = requests.Session()
    session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
    
    client = OpensearchVectorClient(
        endpoint=OPENSEARCH_ENDPOINT,
        index=OPENSEARCH_INDEX,
        dim=dim,
        embedding_field=EMBEDDING_FIELD,
        text_field=TEXT_FIELD,
        engine="nmslib",
        space_type="cosinesimil",
        search_pipeline="knn"
    )
    
    # Initialize vector store and create index
    vector_store = OpensearchVectorStore(client)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context, embed_model=embed_model)
    
    # Save index locally
    with open('index.pkl', 'wb') as f:
        pickle.dump(index, f)
    logger.info("Index created and saved to index.pkl")
    
    return index

def force_update():
    """Force update the index with current documents"""
    try:
        # Setup OpenSearch
        setup_opensearch()
        
        # Process documents
        documents = process_documents()
        if not documents:
            logger.error("No documents found to process")
            return
        
        # Create new index
        create_index(documents)
        logger.info("Force update completed successfully")
        
    except Exception as e:
        logger.error(f"Error during force update: {str(e)}")
        raise

if __name__ == "__main__":
    force_update()