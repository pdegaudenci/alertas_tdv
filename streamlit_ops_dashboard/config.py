import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # AWS Configuration
    AWS_REGION = os.getenv('AWS_REGION', 'eu-west-1')
    AWS_SQS_QUEUE_URL = os.getenv('AWS_SQS_QUEUE_URL')
    AWS_SQS_DLQ_URL = os.getenv('AWS_SQS_DLQ_URL')
    AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET')
    AWS_S3_BRONZE_PREFIX = os.getenv('AWS_S3_BRONZE_PREFIX', 'bronze/trading_alerts/')
    AWS_LAMBDA_FUNCTION_NAME = os.getenv('AWS_LAMBDA_FUNCTION_NAME')

    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    # Java Receiver Configuration
    JAVA_RECEIVER_BASE_URL = os.getenv('JAVA_RECEIVER_BASE_URL')

    @classmethod
    def validate(cls):
        """Validate that required environment variables are set."""
        required = [
            'AWS_SQS_QUEUE_URL',
            'AWS_S3_BUCKET',
            'SUPABASE_URL',
            'SUPABASE_SERVICE_ROLE_KEY',
            'JAVA_RECEIVER_BASE_URL'
        ]
        missing = [var for var in required if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# Validate configuration on import
Config.validate()