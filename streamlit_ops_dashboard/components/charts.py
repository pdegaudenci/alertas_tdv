import streamlit as st
import plotly.express as px
import pandas as pd

def plot_status_distribution(data):
    """Plot distribution of statuses."""
    if not data:
        st.write("No data to plot.")
        return

    df = pd.DataFrame(list(data.items()), columns=['Status', 'Count'])
    fig = px.bar(df, x='Status', y='Count', title='Status Distribution')
    st.plotly_chart(fig, use_container_width=True)

def plot_daily_metrics(metrics):
    """Plot daily metrics as a bar chart."""
    if not metrics:
        st.write("No metrics to plot.")
        return

    # Filter numeric metrics
    numeric_metrics = {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and v > 0}
    if not numeric_metrics:
        st.write("No numeric metrics to plot.")
        return

    df = pd.DataFrame(list(numeric_metrics.items()), columns=['Metric', 'Value'])
    fig = px.bar(df, x='Metric', y='Value', title='Daily Metrics')
    st.plotly_chart(fig, use_container_width=True)

def plot_quality_distribution(distribution):
    """Plot quality distribution."""
    if not distribution:
        st.write("No distribution data.")
        return

    for key, values in distribution.items():
        df = pd.DataFrame(list(values.items()), columns=[key, 'Count'])
        fig = px.pie(df, values='Count', names=key, title=f'Distribution by {key}')
        st.plotly_chart(fig, use_container_width=True)