import asyncio
from qdrant_client.models import Distance, VectorParams, PointStruct

from job_applicator.clients import qdrant, gemini_client
from job_applicator.services.research import RawPosting

COLLECTION_NAME = "jobs"
EMBEDDING_MODEL = "text-embedding-004"
VECTOR_SIZE = 768  # Dimension for text-embedding-004


async def init_qdrant() -> None:
    """Ensure the Qdrant collection exists."""
    collections = await qdrant.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION_NAME not in names:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


async def get_embedding(text: str) -> list[float]:
    """Generate text vector embedding via Gemini API."""
    res = await asyncio.to_thread(
        gemini_client.models.embed_content,
        model=EMBEDDING_MODEL,
        contents=text[:2000],  # Embed title + snippet
    )
    return res.embedding.values


async def filter_duplicates(postings: list[RawPosting], score_threshold: float = 0.85) -> list[RawPosting]:
    """Filter out job postings that already exist in Qdrant based on vector similarity."""
    await init_qdrant()
    unique_postings: list[RawPosting] = []

    for posting in postings:
        vector = await get_embedding(f"{posting.title}\n{posting.content}")
        
        # Search Qdrant for similar vectors
        search_result = await qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=1,
            score_threshold=score_threshold,
        )

        if not search_result:
            # Not a duplicate! Keep it and store in Qdrant
            unique_postings.append(posting)
            await qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=hash(posting.url) & 0x7FFFFFFFFFFFFFFF,  # positive 64-bit ID
                        vector=vector,
                        payload={"url": posting.url, "title": posting.title},
                    )
                ],
            )

    return unique_postings