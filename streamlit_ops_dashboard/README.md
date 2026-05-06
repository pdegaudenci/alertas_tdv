# Trading System Operational Dashboard

A Streamlit-based operational dashboard for monitoring the trading system's health and performance.

## Features

- **Service Health Monitoring**: Real-time status of Java Receiver, AWS SQS, Lambda, Supabase, and S3
- **Daily Metrics**: Alerts received, validations, errors, and processing stats
- **Queue Monitoring**: SQS message counts, backlog detection, DLQ status
- **Data Quality**: Validation rates, confidence scores, distribution analysis
- **Recent Activity**: Latest events, errors, and validation results
- **Auto-refresh**: Configurable automatic data refresh

## Setup

1. **Clone/Create the directory structure**:
   ```
   streamlit_ops_dashboard/
   ├── app.py
   ├── requirements.txt
   ├── .env.example
   ├── README.md
   ├── config.py
   ├── services/
   ├── components/
   └── utils/
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   - Copy `.env.example` to `.env`
   - Fill in your actual values:
     ```bash
     cp .env.example .env
     # Edit .env with your credentials
     ```

4. **Required Environment Variables**:
   ```env
   AWS_REGION=eu-west-1
   AWS_SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/123456789012/trading-alerts-queue
   AWS_SQS_DLQ_URL=https://sqs.eu-west-1.amazonaws.com/123456789012/trading-alerts-dlq
   AWS_S3_BUCKET=trading-lakehouse-btc-s3
   AWS_S3_BRONZE_PREFIX=bronze/trading_alerts/
   AWS_LAMBDA_FUNCTION_NAME=trading-alerts-consumer-container

   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

   JAVA_RECEIVER_BASE_URL=http://trading-webhook-receiver-java.eu-west-1.elasticbeanstalk.com
   ```

## Running Locally

```bash
cd streamlit_ops_dashboard
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

## Security Notes

- Never commit `.env` files to version control
- Use IAM roles with minimal required permissions for AWS access
- Supabase service role key has admin privileges - use carefully
- Ensure network security for production deployments

## Architecture

The dashboard is built with a modular architecture:

- **Services**: Handle external API calls and data fetching
- **Components**: Reusable UI components (cards, tables, charts)
- **Utils**: Helper functions for formatting and safety
- **Caching**: Streamlit caching with appropriate TTL for performance

## Troubleshooting

### Common Issues

1. **AWS Credentials**: Ensure AWS credentials are configured (environment variables, IAM roles, or AWS CLI)
2. **Supabase Connection**: Verify URL and service role key
3. **Java Receiver**: Check if the Elastic Beanstalk app is running and accessible
4. **Permissions**: Ensure AWS IAM user/role has permissions for SQS, S3, Lambda, CloudWatch

### Debugging

- Check Streamlit logs for errors
- Use browser developer tools for network issues
- Verify environment variables are loaded correctly

## Deployment

For production deployment:

1. Use Streamlit Cloud, Heroku, or AWS EC2
2. Configure environment variables in the deployment platform
3. Set up proper logging and monitoring
4. Consider using secrets management services

## Contributing

1. Follow the modular structure
2. Add proper error handling
3. Use caching appropriately
4. Test with mock data if possible