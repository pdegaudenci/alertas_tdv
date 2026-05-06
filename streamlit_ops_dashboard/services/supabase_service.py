from supabase import create_client, Client
import logging
from datetime import datetime, timezone
from config import Config

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)

    def get_daily_metrics(self):
        """Get daily metrics from Supabase tables."""
        try:
            today = datetime.now(timezone.utc).date().isoformat()

            # Alert events today
            alert_events = self.client.table('alert_events').select('*').gte('created_at', today).execute()
            alert_events_count = len(alert_events.data)

            # Validation results today
            validation_results = self.client.table('validation_results').select('*').gte('created_at', today).execute()
            approved = len([r for r in validation_results.data if r.get('approve')])
            rejected = len([r for r in validation_results.data if not r.get('approve')])

            # Error logs today
            error_logs = self.client.table('backend_error_logs').select('*').gte('created_at', today).execute()
            errors_count = len(error_logs.data)

            # Fragment counts by status
            fragments = self.client.table('sqs_alert_fragments').select('status').execute()
            fragment_status_counts = {}
            for frag in fragments.data:
                status = frag.get('status', 'UNKNOWN')
                fragment_status_counts[status] = fragment_status_counts.get(status, 0) + 1

            # Pending pairs
            core_count = fragment_status_counts.get('CORE', 0)
            extra_count = fragment_status_counts.get('EXTRA', 0)
            pending_pairs = min(core_count, extra_count)

            return {
                'status': 'UP',
                'alert_events_today': alert_events_count,
                'validation_approved_today': approved,
                'validation_rejected_today': rejected,
                'errors_today': errors_count,
                'fragment_status_counts': fragment_status_counts,
                'pending_pairs': pending_pairs
            }
        except Exception as e:
            logger.error(f"Error getting Supabase daily metrics: {e}")
            return {'status': 'ERROR', 'error': str(e)}

    def get_recent_events(self, limit=10):
        """Get recent alert events."""
        try:
            response = self.client.table('alert_events').select('*').order('created_at', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []

    def get_recent_validation_results(self, limit=10):
        """Get recent validation results."""
        try:
            response = self.client.table('validation_results').select('*').order('created_at', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting recent validation results: {e}")
            return []

    def get_recent_errors(self, limit=10):
        """Get recent backend errors."""
        try:
            response = self.client.table('backend_error_logs').select('*').order('created_at', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting recent errors: {e}")
            return []

    def get_processing_quality_metrics(self):
        """Get quality metrics from validation results."""
        try:
            response = self.client.table('validation_results').select('probability_tp_before_sl, score_external, validation_confidence, event, side, symbol, tf, approve').execute()
            data = response.data

            if not data:
                return {}

            # Calculate averages
            prob_tp = [d['probability_tp_before_sl'] for d in data if d.get('probability_tp_before_sl') is not None]
            score_ext = [d['score_external'] for d in data if d.get('score_external') is not None]
            val_conf = [d['validation_confidence'] for d in data if d.get('validation_confidence') is not None]

            return {
                'avg_probability_tp_before_sl': sum(prob_tp) / len(prob_tp) if prob_tp else None,
                'avg_score_external': sum(score_ext) / len(score_ext) if score_ext else None,
                'avg_validation_confidence': sum(val_conf) / len(val_conf) if val_conf else None,
                'distribution': self._calculate_distribution(data)
            }
        except Exception as e:
            logger.error(f"Error getting quality metrics: {e}")
            return {}

    def _calculate_distribution(self, data):
        """Calculate distribution by event, side, symbol, tf."""
        dist = {}
        for d in data:
            for key in ['event', 'side', 'symbol', 'tf']:
                value = d.get(key)
                if value:
                    if key not in dist:
                        dist[key] = {}
                    dist[key][value] = dist[key].get(value, 0) + 1
        return dist