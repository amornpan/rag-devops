import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from opensearchpy import OpenSearch, RequestError
from sentence_transformers import SentenceTransformer
import numpy as np
from os import getenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class QueryRequest(BaseModel):
    query: str

# Initialize embedding model
model = SentenceTransformer('BAAI/bge-m3')

# Initialize OpenSearch client
OPENSEARCH_URL = getenv("OPENSEARCH_ENDPOINT", "http://opensearch:9200")
INDEX_NAME = getenv("OPENSEARCH_INDEX", "webinar_pdf_index")

# Configure OpenSearch client
opensearch_client = OpenSearch(
    hosts=[{'host': 'opensearch', 'port': 9200}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

def create_search_query(query_vector: np.ndarray, top_k: int = 3) -> dict:
    """Create a search query for vector similarity search."""
    return {
        "size": top_k,
        "_source": ["content", "metadata"],
        "query": {
            "script_score": {
                "query": {"match_all": {}},
                "script": {
                    "lang": "knn",
                    "source": "knn_score",
                    "params": {
                        "field": "embedding",
                        "query_value": query_vector.tolist(),
                        "space_type": "cosinesimil"
                    }
                }
            }
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        health = opensearch_client.cluster.health()
        index_exists = opensearch_client.indices.exists(INDEX_NAME)
        if index_exists:
            mapping = opensearch_client.indices.get_mapping(INDEX_NAME)
            logger.info(f"Current mapping: {mapping}")
        return {
            "status": "healthy",
            "opensearch_status": health["status"],
            "index_exists": index_exists,
            "mapping": mapping if index_exists else None
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/search")
async def search(request: QueryRequest):
    """Search endpoint that handles vector similarity search."""
    try:
        logger.info(f"Searching for: {request.query}")
        
        # Generate embedding for query
        query_embedding = model.encode(request.query)
        query_embedding = query_embedding.astype(np.float32)  # Convert to float32
        
        # Create search query
        search_query = create_search_query(query_embedding)
        logger.info(f"Executing search query: {search_query}")
        
        # Execute search
        response = opensearch_client.search(
            index=INDEX_NAME,
            body=search_query
        )
        logger.info(f"Got response: {response}")
        
        # Process results
        hits = response["hits"]["hits"]
        results = [
            {
                "text": hit["_source"].get("content", ""),
                "metadata": hit["_source"].get("metadata", {}),
                "score": hit["_score"],
                "file_path": hit["_source"].get("metadata", {}).get("file_path", "N/A")
            }
            for hit in hits
        ]
        
        return {"results": results}
        
    except RequestError as e:
        logger.error(f"OpenSearch request error: {str(e)}")
        error_detail = str(e)
        if "search_phase_execution_exception" in error_detail:
            logger.error("Search phase execution exception - check vector dimensions and index mapping")
        raise HTTPException(status_code=400, detail=f"Search request error: {error_detail}")
    except Exception as e:
        logger.error(f"Error during search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)