"""Optional S3-compatible archive mirror. Authentication remains in the API."""
import io
import os
import zipfile
from pathlib import Path
from .governance import verify_bundle


def archive_bundle(directory: Path, trusted_key: str) -> bytes:
    manifest = verify_bundle(directory, trusted_key)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
        for name in [*manifest["files"], "manifest.json", "manifest.signature.json"]:
            output.writestr(name, (directory / name).read_bytes())
    return buffer.getvalue()


def mirror_release(directory, trusted_key, tenant_id, run_id):
    bucket = os.environ.get("FRAUDSHIELD_S3_BUCKET")
    if not bucket:
        return {"storage": "local", "mirrored": False}
    import boto3
    archive = archive_bundle(directory, trusted_key)
    client = boto3.client("s3", endpoint_url=os.environ.get("FRAUDSHIELD_S3_ENDPOINT"))
    key = "tenants/" + tenant_id + "/releases/" + run_id + "/release.zip"
    client.put_object(Bucket=bucket, Key=key, Body=archive,
                      ContentType="application/zip", ServerSideEncryption="AES256")
    return {"storage": "s3", "mirrored": True, "key": key}
