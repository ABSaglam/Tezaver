"""
MX-25004: Bus Backup CLI

Creates backup/snapshot of bus contents:
- FS: Creates zip archive
- S3: Creates manifest.json with key list

Usage:
    tezaver-bus-backup --bus .tezaver_bus --out backups/BACKUP.zip
    tezaver-bus-backup --bus s3://bucket/prefix --out backups/BACKUP.manifest.json
"""

import argparse
import os
import json
import time
import zipfile
from pathlib import Path
from typing import Optional


def backup_fs_bus(bus_root: str, output_path: str) -> dict:
    """
    Backup FS bus to zip file.
    TR: Dosya sistemi bus'ını zip olarak yedekle.
    """
    bus_path = Path(bus_root)
    
    if not bus_path.exists():
        return {"ok": False, "error": f"Bus not found: {bus_root}"}
        
    # Create output directory
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Collect files
    files_added = 0
    dirs_to_backup = ["artifacts", "events", "jobs", "cloud_registry", "cloud_runtime"]
    
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for dir_name in dirs_to_backup:
            dir_path = bus_path / dir_name
            if dir_path.exists():
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(bus_path)
                        zf.write(file_path, arcname)
                        files_added += 1
                        
        # Add metadata
        metadata = {
            "backup_ts": int(time.time()),
            "bus_root": bus_root,
            "files_count": files_added,
            "backup_version": "1",
        }
        zf.writestr("_backup_manifest.json", json.dumps(metadata, indent=2))
        
    return {
        "ok": True,
        "output_path": str(output),
        "files_count": files_added,
        "backup_ts": metadata["backup_ts"],
    }


def backup_s3_bus(bus_spec: str, output_path: str) -> dict:
    """
    Backup S3 bus to manifest.json.
    TR: S3 bus'ını manifest dosyası olarak yedekle.
    """
    try:
        import boto3
    except ImportError:
        return {"ok": False, "error": "boto3 not installed"}
        
    # Parse S3 URL
    parts = bus_spec[5:].split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    
    # Get credentials from environment
    endpoint_url = os.environ.get("TEZAVER_S3_ENDPOINT_URL")
    access_key = os.environ.get("TEZAVER_S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("TEZAVER_S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    
    client_kwargs = {"service_name": "s3"}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key
        
    client = boto3.client(**client_kwargs)
    
    # List all objects
    keys = []
    paginator = client.get_paginator("list_objects_v2")
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
            })
            
    # Create manifest
    manifest = {
        "backup_ts": int(time.time()),
        "bucket": bucket,
        "prefix": prefix,
        "keys_count": len(keys),
        "keys": keys,
        "backup_version": "1",
    }
    
    # Write manifest
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output, "w") as f:
        json.dump(manifest, f, indent=2)
        
    return {
        "ok": True,
        "output_path": str(output),
        "keys_count": len(keys),
        "backup_ts": manifest["backup_ts"],
    }


def run_backup(bus_spec: str, output_path: str) -> dict:
    """
    Run backup based on bus spec.
    TR: Bus tipine göre yedekleme yap.
    """
    if bus_spec.startswith("s3://"):
        return backup_s3_bus(bus_spec, output_path)
    else:
        return backup_fs_bus(bus_spec, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Tezaver Bus Backup - Yedekleme aracı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  tezaver-bus-backup --bus .tezaver_bus --out backups/BACKUP.zip
  tezaver-bus-backup --bus s3://bucket/prefix --out backups/BACKUP.manifest.json
  
TR: Bu araç, inceleme ve ispat paketi oluşturur.
"""
    )
    parser.add_argument("--bus", required=True, help="Bus path (FS veya S3)")
    parser.add_argument("--out", required=True, help="Output yolu (zip veya manifest.json)")
    
    args = parser.parse_args()
    
    result = run_backup(args.bus, args.out)
    
    if result["ok"]:
        print(f"✅ Yedek alındı: {result['output_path']}")
        print(f"   Dosya sayısı: {result.get('files_count') or result.get('keys_count')}")
        print(f"   Zaman: {result['backup_ts']}")
    else:
        print(f"❌ Hata: {result.get('error')}")
        exit(1)


if __name__ == "__main__":
    main()
