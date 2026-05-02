FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY requirements_lambda.txt .

RUN pip install --no-cache-dir -r requirements_lambda.txt

COPY app ./app
COPY lambda_function.py ./lambda_function.py

CMD ["lambda_function.lambda_handler"]