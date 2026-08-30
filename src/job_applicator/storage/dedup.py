import uuid

from qdrant_client.http.models import Distance, Document, PointStruct, VectorParams

from job_applicator.clients import qdrant
from job_applicator.services.research import RawPosting

COLLECTION_NAME = "jobs"
MODEL_NAME = "sentence-transformers/all-minilm-l6-v2"
VECTOR_SIZE = 384


async def init_qdrant() -> None:
    """Ensure the Qdrant collection exists."""
    collections = await qdrant.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION_NAME not in names:
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


async def filter_duplicates(postings: list[RawPosting], score_threshold: float = 0.85) -> list[RawPosting]:
    """Deduplicate postings using Qdrant Cloud Inference."""
    await init_qdrant()
    unique_postings: list[RawPosting] = []

    for posting in postings:
        text_content = f"{posting.title}\n{posting.content[:1500]}"

        try:
            search_result = await qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=Document(text=text_content, model=MODEL_NAME),
                limit=1,
                score_threshold=score_threshold,
            )

            if not search_result.points:
                unique_postings.append(posting)
                await qdrant.upsert(
                    collection_name=COLLECTION_NAME,
                    points=[
                        PointStruct(
                            id=str(uuid.uuid5(uuid.NAMESPACE_URL, posting.url)),
                            vector=Document(text=text_content, model=MODEL_NAME),
                            payload={"url": posting.url, "title": posting.title},
                        )
                    ],
                )
        except Exception:
            unique_postings.append(posting)

    return unique_postings
