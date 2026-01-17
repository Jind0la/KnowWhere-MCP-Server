"""
Object Storage Service

Provides cloud storage abstraction for document uploads.
Supports AWS S3, Cloudflare R2, and Google Cloud Storage.
"""

import hashlib
import io
from datetime import datetime, timedelta
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import structlog
from botocore.config import Config

from src.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class ObjectStorageService:
    """
    Cloud object storage abstraction.
    
    Supports:
    - AWS S3
    - Cloudflare R2 (S3-compatible)
    - Google Cloud Storage
    
    Features:
    - Upload/download files
    - Generate presigned URLs
    - List and delete objects
    - File metadata management
    """
    
    ALLOWED_MIME_TYPES = {
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        # Images
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/tiff",
    }
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = None
        self._initialized = False
        self._bucket = self.settings.storage_bucket
        self._provider = self.settings.storage_provider
    
    async def connect(self) -> None:
        """Initialize the storage client."""
        if self._initialized:
            return
        
        # Import boto3 lazily to avoid startup cost if not used
        try:
            import aioboto3
        except ImportError:
            logger.error("aioboto3 not installed. Install with: pip install aioboto3")
            raise
        
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )
        
        # Build client config
        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.settings.storage_region,
            "config": config,
        }
        
        # Add credentials if provided
        if self.settings.storage_access_key:
            client_kwargs["aws_access_key_id"] = self.settings.storage_access_key.get_secret_value()
        if self.settings.storage_secret_key:
            client_kwargs["aws_secret_access_key"] = self.settings.storage_secret_key.get_secret_value()
        
        # Custom endpoint for R2/MinIO
        if self.settings.storage_endpoint_url:
            client_kwargs["endpoint_url"] = self.settings.storage_endpoint_url
        
        self._session = aioboto3.Session()
        self._client_kwargs = client_kwargs
        self._initialized = True
        
        logger.info(
            "Storage service initialized",
            provider=self._provider,
            bucket=self._bucket,
        )
    
    async def _get_client(self):
        """Get an S3 client context manager."""
        if not self._initialized:
            await self.connect()
        return self._session.client(**self._client_kwargs)
    
    def _generate_key(self, user_id: UUID, filename: str) -> str:
        """
        Generate a unique object key.
        
        Format: users/{user_id}/files/{date}/{uuid}_{filename}
        """
        date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
        file_uuid = str(uuid4())[:8]
        safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
        
        return f"users/{user_id}/files/{date_prefix}/{file_uuid}_{safe_filename}"
    
    def validate_file(
        self,
        filename: str,
        file_size: int,
        mime_type: str,
    ) -> tuple[bool, str | None]:
        """
        Validate a file before upload.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check MIME type
        if mime_type not in self.ALLOWED_MIME_TYPES:
            return False, f"File type '{mime_type}' not allowed"
        
        # Check file size
        max_size_bytes = self.settings.storage_max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return False, f"File exceeds maximum size of {self.settings.storage_max_file_size_mb}MB"
        
        # Check filename
        if not filename or len(filename) > 255:
            return False, "Invalid filename"
        
        return True, None
    
    async def upload_file(
        self,
        user_id: UUID,
        file_data: bytes | BinaryIO,
        filename: str,
        mime_type: str,
        metadata: dict | None = None,
    ) -> dict:
        """
        Upload a file to object storage.
        
        Args:
            user_id: Owner user ID
            file_data: File content (bytes or file-like object)
            filename: Original filename
            mime_type: MIME type of the file
            metadata: Optional metadata to store with the file
            
        Returns:
            Dict with upload info (key, size, etag, etc.)
        """
        # Validate
        if isinstance(file_data, bytes):
            file_size = len(file_data)
            file_obj = io.BytesIO(file_data)
        else:
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Seek back to start
            file_obj = file_data
        
        is_valid, error = self.validate_file(filename, file_size, mime_type)
        if not is_valid:
            raise ValueError(error)
        
        # Generate key
        object_key = self._generate_key(user_id, filename)
        
        # Calculate checksum
        if isinstance(file_data, bytes):
            checksum = hashlib.sha256(file_data).hexdigest()
        else:
            file_data.seek(0)
            checksum = hashlib.sha256(file_data.read()).hexdigest()
            file_data.seek(0)
            file_obj = file_data
        
        # Prepare metadata
        s3_metadata = {
            "original-filename": filename,
            "user-id": str(user_id),
            "checksum-sha256": checksum,
        }
        if metadata:
            for k, v in metadata.items():
                s3_metadata[f"custom-{k}"] = str(v)
        
        # Upload
        async with await self._get_client() as client:
            response = await client.upload_fileobj(
                file_obj,
                self._bucket,
                object_key,
                ExtraArgs={
                    "ContentType": mime_type,
                    "Metadata": s3_metadata,
                },
            )
            
            # Get object info
            head = await client.head_object(Bucket=self._bucket, Key=object_key)
        
        logger.info(
            "File uploaded",
            user_id=str(user_id),
            key=object_key,
            size=file_size,
        )
        
        return {
            "key": object_key,
            "bucket": self._bucket,
            "size_bytes": file_size,
            "mime_type": mime_type,
            "checksum": checksum,
            "etag": head.get("ETag", "").strip('"'),
            "uploaded_at": datetime.utcnow().isoformat(),
        }
    
    async def download_file(self, object_key: str) -> tuple[bytes, dict]:
        """
        Download a file from object storage.
        
        Returns:
            Tuple of (file_content, metadata)
        """
        async with await self._get_client() as client:
            response = await client.get_object(Bucket=self._bucket, Key=object_key)
            
            content = await response["Body"].read()
            metadata = response.get("Metadata", {})
            
            return content, metadata
    
    async def get_presigned_url(
        self,
        object_key: str,
        expiration: int = 3600,
        download_filename: str | None = None,
    ) -> str:
        """
        Generate a presigned URL for downloading a file.
        
        Args:
            object_key: S3 object key
            expiration: URL expiration in seconds (default 1 hour)
            download_filename: Optional filename for Content-Disposition
            
        Returns:
            Presigned URL string
        """
        params = {
            "Bucket": self._bucket,
            "Key": object_key,
        }
        
        if download_filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'
        
        async with await self._get_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expiration,
            )
        
        return url
    
    async def get_presigned_upload_url(
        self,
        user_id: UUID,
        filename: str,
        mime_type: str,
        expiration: int = 3600,
    ) -> dict:
        """
        Generate a presigned URL for direct upload.
        
        Returns:
            Dict with url, fields for form upload, and the object key
        """
        object_key = self._generate_key(user_id, filename)
        
        async with await self._get_client() as client:
            presigned_post = await client.generate_presigned_post(
                self._bucket,
                object_key,
                Fields={
                    "Content-Type": mime_type,
                },
                Conditions=[
                    {"Content-Type": mime_type},
                    ["content-length-range", 1, self.settings.storage_max_file_size_mb * 1024 * 1024],
                ],
                ExpiresIn=expiration,
            )
        
        return {
            "url": presigned_post["url"],
            "fields": presigned_post["fields"],
            "key": object_key,
            "expires_at": (datetime.utcnow() + timedelta(seconds=expiration)).isoformat(),
        }
    
    async def delete_file(self, object_key: str) -> bool:
        """Delete a file from object storage."""
        try:
            async with await self._get_client() as client:
                await client.delete_object(Bucket=self._bucket, Key=object_key)
            
            logger.info("File deleted", key=object_key)
            return True
        except Exception as e:
            logger.error("Failed to delete file", key=object_key, error=str(e))
            return False
    
    async def delete_user_files(self, user_id: UUID) -> int:
        """
        Delete all files for a user (GDPR deletion).
        
        Returns:
            Number of files deleted
        """
        prefix = f"users/{user_id}/"
        deleted_count = 0
        
        async with await self._get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                if "Contents" not in page:
                    continue
                
                objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                
                if objects:
                    await client.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": objects},
                    )
                    deleted_count += len(objects)
        
        logger.info("User files deleted", user_id=str(user_id), count=deleted_count)
        return deleted_count
    
    async def list_user_files(
        self,
        user_id: UUID,
        prefix: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """List files for a user."""
        full_prefix = f"users/{user_id}/files/{prefix}"
        files = []
        
        async with await self._get_client() as client:
            response = await client.list_objects_v2(
                Bucket=self._bucket,
                Prefix=full_prefix,
                MaxKeys=limit,
            )
            
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"].strip('"'),
                })
        
        return files
    
    async def health_check(self) -> bool:
        """Check if storage service is healthy."""
        try:
            async with await self._get_client() as client:
                await client.head_bucket(Bucket=self._bucket)
            return True
        except Exception as e:
            logger.error("Storage health check failed", error=str(e))
            return False


# Global storage instance
_storage: ObjectStorageService | None = None


async def get_storage() -> ObjectStorageService:
    """Get the global storage service instance."""
    global _storage
    
    if _storage is None:
        _storage = ObjectStorageService()
        await _storage.connect()
    
    return _storage


async def close_storage() -> None:
    """Close the global storage service."""
    global _storage
    _storage = None
