"""
Supabase Storage client — handles raw file uploads and signed URL generation.

Uses the service_role key so we can freely read/write the private
bucket without RLS friction during the assessment.
"""

from __future__ import annotations

from supabase import create_client, Client

from app.config import settings


def _get_client() -> Client:
    """
    Create a Supabase client using the service role key.

    The SUPABASE_URL in .env may contain a /rest/v1/ suffix
    (PostgREST endpoint); the supabase-py client needs the
    bare project URL, so we strip any path suffix.
    """
    url = settings.supabase_url.split("/rest")[0].rstrip("/")
    return create_client(url, settings.supabase_service_role_key)


def upload_raw_file(file_bytes: bytes, storage_path: str, content_type: str) -> str:
    """
    Upload raw file bytes to the Supabase Storage bucket.

    Parameters
    ----------
    file_bytes   : raw bytes of the file
    storage_path : path inside the bucket, e.g. "abc-123/report.pdf"
    content_type : MIME type, e.g. "application/pdf"

    Returns
    -------
    The storage path that was written (same as input).
    """
    client = _get_client()
    bucket = client.storage.from_(settings.supabase_bucket)

    # Upload (upsert=True overwrites if re-uploading same doc)
    bucket.upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"},
    )

    return storage_path


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """
    Generate a temporary signed URL for the file so the frontend
    can display / download the original document.

    Parameters
    ----------
    storage_path : path inside the bucket
    expires_in   : seconds until the URL expires (default 1 hour)

    Returns
    -------
    Signed URL string.
    """
    client = _get_client()
    bucket = client.storage.from_(settings.supabase_bucket)
    response = bucket.create_signed_url(storage_path, expires_in)
    return response["signedURL"]
