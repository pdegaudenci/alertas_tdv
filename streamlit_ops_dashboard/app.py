import streamlit as st
import time
import logging
from components.layout import (
    setup_page, create_sidebar_controls, display_service_status_section,
    display_daily_metrics_section, display_sqs_section, display_recent_data_section
)
from components.charts import plot_daily_metrics, plot_status_distribution, plot_quality_distribution
from services.receiver_health_service import ReceiverHealthService
from services.aws_sqs_service import AWSSQSService
from services.aws_s3_service import AWSS3Service
from services.aws_lambda_service import AWSLambdaService
from services.supabase_service import SupabaseService
from utils.safe import handle_service_error

# Setup logging
logging.basicConfig(level=logging.INFO)

# Cache functions with TTL
@st.cache_data(ttl=10)
def get_service_statuses():
    """Get status of all services."""
    statuses = {}

    # Java Receiver
    try:
        statuses['Java Receiver'] = ReceiverHealthService.check_health()
    except Exception as e:
        statuses['Java Receiver'] = handle_service_error('Java Receiver', e)

    # SQS
    try:
        sqs_service = AWSSQSService()
        statuses['SQS'] = sqs_service.get_main_queue_metrics()
    except Exception as e:
        statuses['SQS'] = handle_service_error('SQS', e)

    # Lambda
    try:
        lambda_service = AWSLambdaService()
        statuses['Lambda'] = lambda_service.get_lambda_metrics()
    except Exception as e:
        statuses['Lambda'] = handle_service_error('Lambda', e)

    # Supabase
    try:
        supabase_service = SupabaseService()
        # Simple health check by trying to get data
        test_data = supabase_service.get_recent_events(limit=1)
        statuses['Supabase'] = {'status': 'UP'} if test_data is not None else {'status': 'DOWN'}
    except Exception as e:
        statuses['Supabase'] = handle_service_error('Supabase', e)

    # S3
    try:
        s3_service = AWSS3Service()
        s3_data = s3_service.list_bronze_files_today()
        statuses['S3'] = {'status': s3_data.get('status', 'DOWN')}
    except Exception as e:
        statuses['S3'] = handle_service_error('S3', e)

    return statuses

@st.cache_data(ttl=15)
def get_supabase_metrics():
    """Get metrics from Supabase."""
    try:
        service = SupabaseService()
        daily = service.get_daily_metrics()
        quality = service.get_processing_quality_metrics()
        return daily, quality
    except Exception as e:
        return handle_service_error('Supabase Metrics', e), {}

@st.cache_data(ttl=30)
def get_s3_metrics():
    """Get S3 metrics."""
    try:
        service = AWSS3Service()
        return service.list_bronze_files_today()
    except Exception as e:
        return handle_service_error('S3 Metrics', e)

@st.cache_data(ttl=15)
def get_recent_data():
    """Get recent data from Supabase."""
    try:
        service = SupabaseService()
        events = service.get_recent_events(limit=10)
        errors = service.get_recent_errors(limit=10)
        validations = service.get_recent_validation_results(limit=10)
        return events, errors, validations
    except Exception as e:
        return [], [], []

def main():
    setup_page()

    # Sidebar controls
    controls = create_sidebar_controls()

    # Auto-refresh
    if controls['auto_refresh'] > 0:
        time.sleep(controls['auto_refresh'])
        st.rerun()

    # Get data
    with st.spinner("Loading data..."):
        service_statuses = get_service_statuses()
        supabase_metrics, quality_metrics = get_supabase_metrics()
        s3_metrics = get_s3_metrics()
        recent_events, recent_errors, recent_validations = get_recent_data()

    # Display sections
    display_service_status_section(service_statuses)
    display_daily_metrics_section(supabase_metrics)
    display_sqs_section(service_statuses.get('SQS', {}))

    # S3 Section
    st.header("☁️ S3 Bronze Export")
    if s3_metrics.get('status') == 'UP':
        st.success("S3 is UP")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Files Today", s3_metrics.get('files_count', 0))
        with col2:
            last_file = s3_metrics.get('last_file')
            if last_file:
                st.metric("Last File", last_file['key'].split('/')[-1])
    else:
        st.error(f"S3 Status: {s3_metrics.get('status')}")

    # Charts
    st.header("📊 Charts")
    col1, col2 = st.columns(2)
    with col1:
        plot_daily_metrics(supabase_metrics)
    with col2:
        plot_quality_distribution(quality_metrics.get('distribution', {}))

    # Recent Data
    display_recent_data_section(recent_events, recent_errors, recent_validations)

    # Footer
    st.markdown("---")
    st.caption("Dashboard refreshes automatically. Last updated: " + time.strftime("%Y-%m-%d %H:%M:%S UTC"))

if __name__ == "__main__":
    main()