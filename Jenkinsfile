pipeline {
    agent any

    environment {
        AWS_REGION = 'eu-west-1'
        AWS_ACCOUNT_ID = '221033227591'

        BACKEND_DIR = 'backend'
        JAVA_SERVICE_DIR = 'trading-webhook-receiver-java'

        ECR_REPOSITORY = 'trading-webhook-receiver-java'

        EB_APPLICATION_NAME = 'trading-webhook-receiver-java-env'
        EB_ENVIRONMENT_NAME = 'Trading-webhook-receiver-java-en-env'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Backend - Install & Test') {
            steps {
                dir("${BACKEND_DIR}") {
                    sh '''
                        python3 -m venv .venv
                        . .venv/bin/activate
                        python -m pip install --upgrade pip
                        pip install -r requirements.txt
                        pip install -r requirements-dev.txt
                        ruff check .
                        pytest --cov=app --cov-report=xml
                    '''
                }
            }
        }

        stage('Java Receiver - Test') {
            steps {
                dir("${JAVA_SERVICE_DIR}") {
                    sh '''
                        chmod +x mvnw
                        ./mvnw test
                    '''
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('sonarqube') {
                    sh '''
                        sonar-scanner
                    '''
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Docker Build & Push ECR') {
            steps {
                dir("${JAVA_SERVICE_DIR}") {
                    sh '''
                        IMAGE_TAG="${GIT_COMMIT}"
                        IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}"

                        aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

                        docker build -t "${IMAGE_URI}" .
                        docker push "${IMAGE_URI}"

                        echo "${IMAGE_URI}" > ../image_uri.txt
                        echo "${IMAGE_TAG}" > ../image_tag.txt
                    '''
                }
            }
        }

        stage('Deploy Elastic Beanstalk Docker') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    IMAGE_URI=$(cat image_uri.txt)
                    VERSION_LABEL="jenkins-java-receiver-${BUILD_NUMBER}"
                    EB_BUCKET="elasticbeanstalk-${AWS_REGION}-${AWS_ACCOUNT_ID}"
                    EB_KEY="trading-webhook-receiver-java/${VERSION_LABEL}.zip"

                    PREVIOUS_VERSION=$(aws elasticbeanstalk describe-environments \
                      --environment-names "${EB_ENVIRONMENT_NAME}" \
                      --query "Environments[0].VersionLabel" \
                      --output text)

                    echo "${PREVIOUS_VERSION}" > previous_eb_version.txt

                    rm -rf eb-bundle
                    mkdir eb-bundle

                    cat > eb-bundle/Dockerrun.aws.json <<EOF
                    {
                      "AWSEBDockerrunVersion": "1",
                      "Image": {
                        "Name": "${IMAGE_URI}",
                        "Update": "true"
                      },
                      "Ports": [
                        {
                          "ContainerPort": 8080
                        }
                      ]
                    }
EOF

                    cd eb-bundle
                    zip -r "../${VERSION_LABEL}.zip" .
                    cd ..

                    aws s3 cp "${VERSION_LABEL}.zip" "s3://${EB_BUCKET}/${EB_KEY}"

                    aws elasticbeanstalk create-application-version \
                      --application-name "${EB_APPLICATION_NAME}" \
                      --version-label "${VERSION_LABEL}" \
                      --source-bundle S3Bucket="${EB_BUCKET}",S3Key="${EB_KEY}"

                    aws elasticbeanstalk update-environment \
                      --environment-name "${EB_ENVIRONMENT_NAME}" \
                      --version-label "${VERSION_LABEL}"

                    aws elasticbeanstalk wait environment-updated \
                      --environment-names "${EB_ENVIRONMENT_NAME}"
                '''
            }
        }

        stage('Post Deploy Health Check') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    CNAME=$(aws elasticbeanstalk describe-environments \
                      --environment-names "${EB_ENVIRONMENT_NAME}" \
                      --query "Environments[0].CNAME" \
                      --output text)

                    curl -f "http://${CNAME}/actuator/health"
                '''
            }
        }
    }

    post {
        failure {
            sh '''
                if [ -f previous_eb_version.txt ]; then
                  PREVIOUS_VERSION=$(cat previous_eb_version.txt)

                  if [ -n "${PREVIOUS_VERSION}" ] && [ "${PREVIOUS_VERSION}" != "None" ]; then
                    echo "Rolling back EB to ${PREVIOUS_VERSION}"

                    aws elasticbeanstalk update-environment \
                      --environment-name "${EB_ENVIRONMENT_NAME}" \
                      --version-label "${PREVIOUS_VERSION}"
                  fi
                fi
            '''
        }

        success {
            echo 'Pipeline completed successfully.'
        }
    }
}