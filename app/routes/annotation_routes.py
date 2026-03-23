"""
Annotation Routes
Handles CRUD operations for 3D scene annotations tied to GPR jobs.
"""
from fastapi import APIRouter, HTTPException, Cookie
from typing import Optional

from app.database import get_db
from app.models import AnnotationCreate, AnnotationUpdate
from app.routes.auth_routes import get_current_user


router = APIRouter(prefix="/api/annotations", tags=["Annotations"])


@router.get("/{job_id}")
async def list_annotations(job_id: str, access_token: Optional[str] = Cookie(None)):
    """
    List all annotations for a specific job.

    Args:
        job_id: Job identifier
        access_token: JWT token from cookie

    Returns:
        List of annotation dictionaries
    """
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, job_id, user_email, ann_type, label, color, note,
                   positions, metadata, created_at
            FROM annotations
            WHERE job_id = %s AND user_email = %s
            ORDER BY created_at DESC
            """,
            (job_id, user)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        annotations = []
        for row in rows:
            annotations.append({
                "id": row[0],
                "job_id": row[1],
                "user_email": row[2],
                "ann_type": row[3],
                "label": row[4],
                "color": row[5],
                "note": row[6],
                "positions": row[7],   # JSON string stored as TEXT
                "metadata": row[8],    # JSON string stored as TEXT
                "created_at": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else ""
            })
        return annotations
    except Exception as e:
        print(f"Error listing annotations: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.post("/{job_id}")
async def create_annotation(
    job_id: str,
    payload: AnnotationCreate,
    access_token: Optional[str] = Cookie(None)
):
    """
    Create a new annotation for a job.

    Args:
        job_id: Job identifier
        payload: Annotation data
        access_token: JWT token from cookie

    Returns:
        Created annotation with its new id
    """
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO annotations
                (job_id, user_email, ann_type, label, color, note, positions, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                job_id,
                user,
                payload.ann_type,
                payload.label,
                payload.color,
                payload.note,
                payload.positions,
                payload.metadata
            )
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return {
            "success": True,
            "id": row[0],
            "created_at": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else ""
        }
    except Exception as e:
        print(f"Error creating annotation: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.put("/{job_id}/{ann_id}")
async def update_annotation(
    job_id: str,
    ann_id: int,
    payload: AnnotationUpdate,
    access_token: Optional[str] = Cookie(None)
):
    """
    Update an existing annotation's label, note, or color.

    Args:
        job_id: Job identifier
        ann_id: Annotation ID
        payload: Fields to update
        access_token: JWT token from cookie

    Returns:
        Success status
    """
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE annotations
            SET label = %s, color = %s, note = %s
            WHERE id = %s AND job_id = %s AND user_email = %s
            """,
            (payload.label, payload.color, payload.note, ann_id, job_id, user)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True}
    except Exception as e:
        print(f"Error updating annotation: {e}")
        raise HTTPException(status_code=500, detail="Database error")


@router.delete("/{job_id}/{ann_id}")
async def delete_annotation(
    job_id: str,
    ann_id: int,
    access_token: Optional[str] = Cookie(None)
):
    """
    Delete an annotation by ID.

    Args:
        job_id: Job identifier
        ann_id: Annotation ID
        access_token: JWT token from cookie

    Returns:
        Success status
    """
    user = get_current_user(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM annotations WHERE id = %s AND job_id = %s AND user_email = %s",
            (ann_id, job_id, user)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True}
    except Exception as e:
        print(f"Error deleting annotation: {e}")
        raise HTTPException(status_code=500, detail="Database error")


__all__ = ["router"]
