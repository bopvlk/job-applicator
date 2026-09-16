import logging
import uuid

from qdrant_client.http.models import Distance, Document, PointStruct, VectorParams

from job_applicator.clients import qdrant
from job_applicator.services.research import RawPosting

logger = logging.getLogger(__name__)

COLLECTION_NAME = "jobs"
MODEL_NAME = "sentence-transformers/all-minilm-l6-v2"
VECTOR_SIZE = 384


async def init_qdrant() -> None:
    """Ensure the Qdrant collection exists."""
    logger.info(
        "Checking Qdrant collection existence",
        extra={"event": "qdrant_check_collection", "collection": COLLECTION_NAME},
    )
    try:
        collections = await qdrant.get_collections()
        names = [c.name for c in collections.collections]
        if COLLECTION_NAME not in names:
            logger.info(
                "Creating new Qdrant vector collection",
                extra={
                    "event": "qdrant_collection_created",
                    "collection": COLLECTION_NAME,
                    "vector_size": VECTOR_SIZE,
                    "distance": "cosine",
                },
            )
            await qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
    except Exception as e:
        logger.error(
            "Failed to initialize Qdrant collection",
            exc_info=True,
            extra={"event": "qdrant_init_error", "error": str(e)},
        )


async def filter_duplicates(postings: list[RawPosting], score_threshold: float = 0.85) -> list[RawPosting]:
    """Deduplicate postings using Qdrant Cloud Inference."""
    await init_qdrant()
    unique_postings: list[RawPosting] = []

    logger.info(
        "Starting vector deduplication batch",
        extra={
            "event": "dedup_batch_started",
            "postings_count": len(postings),
            "similarity_threshold": score_threshold,
        },
    )

    for posting in postings:
        text_content = f"{posting.title}\n{posting.content[:1500]}"

        try:
            search_result = await qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=Document(text=text_content, model=MODEL_NAME),
                limit=1,
                score_threshold=score_threshold,
            )

            if search_result.points:
                similarity = search_result.points[0].score
                logger.info(
                    "Duplicate job posting detected and dropped",
                    extra={
                        "event": "duplicate_job_dropped",
                        "url": posting.url,
                        "title": posting.title,
                        "similarity_score": similarity,
                    },
                )
            else:
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
                logger.info(
                    "Unique job posting embedded and stored in Qdrant",
                    extra={
                        "event": "unique_job_upserted",
                        "url": posting.url,
                        "title": posting.title,
                    },
                )
        except Exception as e:
            logger.error(
                "Qdrant vector query/upsert failed for posting",
                exc_info=True,
                extra={"event": "qdrant_query_error", "url": posting.url, "error": str(e)},
            )
            unique_postings.append(posting)

    logger.info(
        "Completed vector deduplication batch",
        extra={
            "event": "dedup_batch_completed",
            "input_count": len(postings),
            "unique_count": len(unique_postings),
            "duplicates_dropped": len(postings) - len(unique_postings),
        },
    )
    return unique_postings
