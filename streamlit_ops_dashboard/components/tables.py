import streamlit as st
import pandas as pd
from utils.formatting import format_timestamp

def display_recent_events(events):
    """Display recent alert events in a table."""
    if not events:
        st.write("No recent events.")
        return

    df = pd.DataFrame(events)
    if 'created_at' in df.columns:
        df['created_at'] = df['created_at'].apply(format_timestamp)

    # Select relevant columns
    columns = ['created_at', 'event_uid', 'symbol', 'tf', 'event', 'side']
    df_display = df[columns] if all(col in df.columns for col in columns) else df

    st.dataframe(df_display, use_container_width=True)

def display_recent_errors(errors):
    """Display recent backend errors in a table."""
    if not errors:
        st.write("No recent errors.")
        return

    df = pd.DataFrame(errors)
    if 'created_at' in df.columns:
        df['created_at'] = df['created_at'].apply(format_timestamp)

    # Select relevant columns
    columns = ['created_at', 'stage', 'error_type', 'message', 'event_uid']
    df_display = df[columns] if all(col in df.columns for col in columns) else df

    st.dataframe(df_display, use_container_width=True)

def display_validation_results(results):
    """Display recent validation results in a table."""
    if not results:
        st.write("No recent validation results.")
        return

    df = pd.DataFrame(results)
    if 'created_at' in df.columns:
        df['created_at'] = df['created_at'].apply(format_timestamp)

    # Select relevant columns
    columns = ['created_at', 'event_uid', 'approve', 'probability_tp_before_sl', 'score_external', 'validation_confidence']
    df_display = df[columns] if all(col in df.columns for col in columns) else df

    st.dataframe(df_display, use_container_width=True)