from sqlalchemy import delete, select

import models
from database import SessionLocal


def upsert_document_chunks(
    user_id: int,
    document_id: int,
    filename: str,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(models.DocumentChunk).where(
                models.DocumentChunk.user_id == user_id,
                models.DocumentChunk.document_id == document_id,
            )
        )
        db.add_all(
            [
                models.DocumentChunk(
                    user_id=user_id,
                    document_id=document_id,
                    source=filename,
                    chunk_index=index,
                    content=chunk,
                    embedding=embedding,
                )
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
            ]
        )
        db.commit()
    finally:
        db.close()


def delete_document_chunks(user_id: int, document_id: int) -> None:
    db = SessionLocal()
    try:
        db.execute(
            delete(models.DocumentChunk).where(
                models.DocumentChunk.user_id == user_id,
                models.DocumentChunk.document_id == document_id,
            )
        )
        db.commit()
    finally:
        db.close()


def search_similar_chunks(
    user_id: int,
    query_embedding: list[float],
    top_k: int = 4,
    document_id: int | None = None,
) -> list[dict]:
    db = SessionLocal()
    try:
        stmt = (
            select(
                models.DocumentChunk.content,
                models.DocumentChunk.source,
                models.DocumentChunk.document_id,
                models.DocumentChunk.user_id,
                models.DocumentChunk.chunk_index,
            )
            .where(models.DocumentChunk.user_id == user_id)
            .order_by(models.DocumentChunk.embedding.l2_distance(query_embedding))
            .limit(max(1, min(top_k, 4)))
        )
        if document_id is not None:
            stmt = stmt.where(models.DocumentChunk.document_id == document_id)

        rows = db.execute(stmt).all()
        return [
            {
                "text": row.content,
                "source": row.source,
                "document_id": row.document_id,
                "user_id": row.user_id,
                "chunk_index": row.chunk_index,
            }
            for row in rows
        ]
    finally:
        db.close()
