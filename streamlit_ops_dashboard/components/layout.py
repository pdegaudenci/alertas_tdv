import streamlit as st

def setup_page():
    """Setup the Streamlit page configuration."""
    st.set_page_config(
        page_title="Trading System Ops Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 Trading System Operational Dashboard")
    st.markdown("---")

def create_sidebar_controls():
    """Create sidebar controls for refresh and filters."""
    st.sidebar.header("Controls")

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # Auto-refresh
    auto_refresh_options = [0, 5, 10, 30]  # seconds
    auto_refresh = st.sidebar.selectbox(
        "Auto-refresh interval (seconds)",
        auto_refresh_options,
        index=2  # Default to 10
    )

    # Filters
    st.sidebar.header("Filters")
    date_filter = st.sidebar.date_input("Date")
    symbol_filter = st.sidebar.text_input("Symbol")
    tf_filter = st.sidebar.text_input("Timeframe")
    event_filter = st.sidebar.text_input("Event")
    side_filter = st.sidebar.selectbox("Side", ["", "BUY", "SELL"])

    # Mode
    mode = st.sidebar.radio("Mode", ["Compact", "Detail"], index=1)

    return {
        'auto_refresh': auto_refresh,
        'date_filter': date_filter,
        'symbol_filter': symbol_filter,
        'tf_filter': tf_filter,
        'event_filter': event_filter,
        'side_filter': side_filter,
        'mode': mode
    }

def display_service_status_section(services_status):
    """Display the service status section."""
    st.header("🔍 Service Status")

    cols = st.columns(len(services_status))
    for i, (service, status) in enumerate(services_status.items()):
        with cols[i]:
            from components.cards import status_card
            status_card(service, status.get('status'), status.get('details'))

def display_daily_metrics_section(metrics):
    """Display the daily metrics section."""
    st.header("📈 Daily Metrics")

    cols = st.columns(4)
    metrics_to_show = [
        ('Alerts Received', metrics.get('alert_events_today', 0)),
        ('Validations Approved', metrics.get('validation_approved_today', 0)),
        ('Validations Rejected', metrics.get('validation_rejected_today', 0)),
        ('Errors Today', metrics.get('errors_today', 0))
    ]

    for i, (title, value) in enumerate(metrics_to_show):
        with cols[i]:
            from components.cards import metric_card
            metric_card(title, value)

def display_sqs_section(sqs_metrics):
    """Display SQS metrics section."""
    st.header("📨 SQS Queue Status")

    if sqs_metrics.get('status') == 'UP':
        st.success("SQS is UP")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Messages", sqs_metrics.get('approximate_number_of_messages', 0))
        with col2:
            st.metric("Not Visible", sqs_metrics.get('approximate_number_of_messages_not_visible', 0))
        with col3:
            st.metric("Delayed", sqs_metrics.get('approximate_number_of_messages_delayed', 0))

        if sqs_metrics.get('has_backlog'):
            st.warning("Queue has backlog")
    else:
        st.error(f"SQS Status: {sqs_metrics.get('status')}")

def display_recent_data_section(recent_events, recent_errors, recent_validations):
    """Display recent data tables."""
    st.header("📋 Recent Data")

    tab1, tab2, tab3 = st.tabs(["Recent Events", "Recent Errors", "Validation Results"])

    with tab1:
        from components.tables import display_recent_events
        display_recent_events(recent_events)

    with tab2:
        from components.tables import display_recent_errors
        display_recent_errors(recent_errors)

    with tab3:
        from components.tables import display_validation_results
        display_validation_results(recent_validations)