import boto3
import logging
from config import Config

logger = logging.getLogger(__name__)

class AWSSQSService:
    def __init__(self):
        self.sqs = boto3.client('sqs', region_name=Config.AWS_REGION)

    def get_queue_attributes(self, queue_url):
        """Get attributes for a specific SQS queue."""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            return response.get('Attributes', {})
        except Exception as e:
            logger.error(f"Error getting SQS attributes for {queue_url}: {e}")
            return {}

    def get_main_queue_metrics(self):
        """Get metrics for the main SQS queue."""
        if not Config.AWS_SQS_QUEUE_URL:
            return {'status': 'ERROR', 'error': 'Queue URL not configured'}

        attrs = self.get_queue_attributes(Config.AWS_SQS_QUEUE_URL)
        if not attrs:
            return {'status': 'DOWN'}

        return {
            'status': 'UP',
            'approximate_number_of_messages': int(attrs.get('ApproximateNumberOfMessages', 0)),
            'approximate_number_of_messages_not_visible': int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0)),
            'approximate_number_of_messages_delayed': int(attrs.get('ApproximateNumberOfMessagesDelayed', 0)),
            'has_backlog': int(attrs.get('ApproximateNumberOfMessages', 0)) > 0,
            'pending_ratio': self._calculate_pending_ratio(attrs)
        }

    def get_dlq_metrics(self):
        """Get metrics for the DLQ if configured."""
        if not Config.AWS_SQS_DLQ_URL:
            return {'status': 'NOT_CONFIGURED'}

        attrs = self.get_queue_attributes(Config.AWS_SQS_DLQ_URL)
        if not attrs:
            return {'status': 'DOWN'}

        return {
            'status': 'UP',
            'approximate_number_of_messages': int(attrs.get('ApproximateNumberOfMessages', 0))
        }

    def _calculate_pending_ratio(self, attrs):
        """Calculate the ratio of pending messages."""
        visible = int(attrs.get('ApproximateNumberOfMessages', 0))
        not_visible = int(attrs.get('ApproximateNumberOfMessagesNotVisible', 0))
        total = visible + not_visible
        return (not_visible / total) * 100 if total > 0 else 0