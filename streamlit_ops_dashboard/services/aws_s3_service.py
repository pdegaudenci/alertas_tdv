import boto3
import logging
from datetime import datetime, timezone
from config import Config

logger = logging.getLogger(__name__)

class AWSS3Service:
    def __init__(self):
        self.s3 = boto3.client('s3', region_name=Config.AWS_REGION)

    def list_bronze_files_today(self):
        """List JSONL files generated today in the bronze prefix."""
        try:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            prefix = f"{Config.AWS_S3_BRONZE_PREFIX}{today}/"

            response = self.s3.list_objects_v2(
                Bucket=Config.AWS_S3_BUCKET,
                Prefix=prefix
            )

            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.jsonl'):
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified']
                        })

            # Get partitions
            partitions = self._get_partitions(prefix)

            return {
                'status': 'UP',
                'files_count': len(files),
                'files': files,
                'partitions': partitions,
                'last_file': max(files, key=lambda x: x['last_modified']) if files else None
            }
        except Exception as e:
            logger.error(f"Error listing S3 bronze files: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    def _get_partitions(self, prefix):
        """Extract unique partitions from file keys."""
        try:
            response = self.s3.list_objects_v2(
                Bucket=Config.AWS_S3_BUCKET,
                Prefix=prefix,
                Delimiter='/'
            )

            partitions = {}
            if 'CommonPrefixes' in response:
                for prefix_obj in response['CommonPrefixes']:
                    parts = prefix_obj['Prefix'].replace(prefix, '').strip('/').split('/')
                    if len(parts) >= 4:  # processing_date, symbol, tf, message_type
                        processing_date, symbol, tf, message_type = parts[:4]
                        key = f"{processing_date}/{symbol}/{tf}/{message_type}"
                        partitions[key] = partitions.get(key, 0) + 1

            return partitions
        except Exception as e:
            logger.error(f"Error getting partitions: {e}")
            return {}