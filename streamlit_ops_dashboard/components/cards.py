import streamlit as st

def status_card(title, status, details=None):
    """Display a status card with color coding."""
    if status == 'UP':
        color = 'green'
        icon = '✅'
    elif status == 'DOWN':
        color = 'red'
        icon = '❌'
    elif status == 'ERROR':
        color = 'orange'
        icon = '⚠️'
    else:
        color = 'gray'
        icon = '❓'

    st.markdown(f"""
    <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin: 5px;">
        <h4>{icon} {title}</h4>
        <p>Status: {status}</p>
        {f'<p>{details}</p>' if details else ''}
    </div>
    """, unsafe_allow_html=True)

def metric_card(title, value, subtitle=None):
    """Display a metric card."""
    st.markdown(f"""
    <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin: 5px;">
        <h4>{title}</h4>
        <p style="font-size: 24px; font-weight: bold;">{value}</p>
        {f'<p>{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)