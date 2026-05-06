import boto3
import logging
from datetime import datetime, timedelta, timezone
from config import Config

logger = logging.getLogger(__name__)

class AWSLambdaService:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch', region_name=Config.AWS_REGION)
        self.lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)

    def get_lambda_metrics(self):
        """Get recent metrics for the Lambda function."""
        try:
            function_name = Config.AWS_LAMBDA_FUNCTION_NAME
            if not function_name:
                return {'status': 'ERROR', 'error': 'Function name not configured'}

            # Check if function exists
            try:
                self.lambda_client.get_function(FunctionName=function_name)
                status = 'UP'
            except self.lambda_client.exceptions.ResourceNotFoundException:
                return {'status': 'DOWN', 'error': 'Function not found'}

            # Get CloudWatch metrics for the last hour
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=1)

            # Invocations
            invocations = self._get_metric('Invocations', start_time, end_time)

            # Errors
            errors = self._get_metric('Errors', start_time, end_time)

            # Duration
            duration = self._get_metric('Duration', start_time, end_time)

            return {
                'status': status,
                'invocations': invocations,
                'errors': errors,
                'average_duration': duration.get('Average', 0) if duration else 0
            }
        except Exception as e:
            logger.error(f"Error getting Lambda metrics: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    def _get_metric(self, metric_name, start_time, end_time):
        """Get a specific CloudWatch metric."""
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'FunctionName',
                        'Value': Config.AWS_LAMBDA_FUNCTION_NAME
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour
                Statistics=['Sum', 'Average', 'Maximum']
            )
            datapoints = response.get('Datapoints', [])
            return datapoints[0] if datapoints else {}
        except Exception as e:
            logger.error(f"Error getting metric {metric_name}: {e}")
            return {}