import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

class ReceiverHealthService:
    @staticmethod
    def check_health():
        """Check the health of the Java Receiver service."""
        try:
            # Check /actuator/health
            actuator_url = f"{Config.JAVA_RECEIVER_BASE_URL}/actuator/health"
            actuator_response = requests.get(actuator_url, timeout=5)
            actuator_status = actuator_response.json().get('status', 'UNKNOWN') if actuator_response.status_code == 200 else 'DOWN'

            # Check /healthz
            healthz_url = f"{Config.JAVA_RECEIVER_BASE_URL}/healthz"
            healthz_response = requests.get(healthz_url, timeout=5)
            healthz_status = 'UP' if healthz_response.status_code == 200 else 'DOWN'

            overall_status = 'UP' if actuator_status == 'UP' and healthz_status == 'UP' else 'DOWN'

            return {
                'status': overall_status,
                'actuator_health': actuator_status,
                'healthz': healthz_status,
                'details': {
                    'actuator_url': actuator_url,
                    'healthz_url': healthz_url
                }
            }
        except Exception as e:
            logger.error(f"Error checking Java Receiver health: {e}")
            return {
                'status': 'ERROR',
                'error': str(e),
                'details': {}
            }