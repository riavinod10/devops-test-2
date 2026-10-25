pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
    }

    environment {
        APP_VERSION    = '1.0.0'
        BACKEND_IMAGE  = 'payment-backend'
        FRONTEND_IMAGE = 'payment-frontend'
        TEST_IMAGE     = "payment-backend:test-${env.BUILD_NUMBER}"
        TEST_CONTAINER = "pb-test-${env.BUILD_NUMBER}"
        SMOKE_BACKEND  = "pb-smoke-${env.BUILD_NUMBER}"
    }

    stages {
        stage('Preflight') {
            steps {
                sh '''
                    set -e
                    echo "Branch/commit: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || true) $(git rev-parse --short HEAD)"
                    docker version --format 'Docker client {{.Client.Version}} / server {{.Server.Version}}'
                '''
            }
        }

        stage('Build') {
            steps {
                echo 'Installing dependencies and compiling sources inside the build image'
                sh 'docker build --target test -t "$TEST_IMAGE" backend'
            }
        }

        stage('Test') {
            steps {
                sh '''
                    set -e
                    docker rm -f "$TEST_CONTAINER" >/dev/null 2>&1 || true
                    docker run --name "$TEST_CONTAINER" "$TEST_IMAGE"
                '''
            }
            post {
                always {
                    sh '''
                        rm -rf reports && mkdir -p reports
                        docker cp "$TEST_CONTAINER":/app/reports/junit.xml reports/junit.xml || true
                        docker rm -f "$TEST_CONTAINER" >/dev/null 2>&1 || true
                    '''
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                }
            }
        }

        stage('Package Containers') {
            parallel {
                stage('Backend image') {
                    steps {
                        sh '''
                            set -e
                            docker build --target runtime --build-arg APP_VERSION="$APP_VERSION" \
                                -t "$BACKEND_IMAGE:$APP_VERSION" \
                                -t "$BACKEND_IMAGE:build-$BUILD_NUMBER" \
                                -t "$BACKEND_IMAGE:latest" backend
                        '''
                    }
                }
                stage('Frontend image') {
                    steps {
                        sh '''
                            set -e
                            docker build \
                                -t "$FRONTEND_IMAGE:$APP_VERSION" \
                                -t "$FRONTEND_IMAGE:build-$BUILD_NUMBER" \
                                -t "$FRONTEND_IMAGE:latest" frontend
                        '''
                    }
                }
            }
        }

        stage('Smoke Test Images') {
            steps {
                sh '''
                    set -e
                    docker rm -f "$SMOKE_BACKEND" >/dev/null 2>&1 || true
                    docker run -d --name "$SMOKE_BACKEND" "$BACKEND_IMAGE:$APP_VERSION"
                    for i in $(seq 1 20); do
                        if docker exec "$SMOKE_BACKEND" python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).read().decode())"; then
                            ok=1; break
                        fi
                        sleep 2
                    done
                    [ "${ok:-0}" = "1" ] || { echo "Backend smoke test failed"; docker logs "$SMOKE_BACKEND"; exit 1; }

                    # Frontend: render nginx template and validate config (backend host mapped locally)
                    docker run --rm --add-host payment-backend:127.0.0.1 "$FRONTEND_IMAGE:$APP_VERSION" nginx -t
                '''
            }
            post {
                always {
                    sh 'docker rm -f "$SMOKE_BACKEND" >/dev/null 2>&1 || true'
                }
            }
        }
    }

    post {
        always {
            sh 'docker rmi "$TEST_IMAGE" >/dev/null 2>&1 || true'
        }
        success {
            sh 'docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.CreatedSince}}" | grep -E "REPOSITORY|payment-(backend|frontend)" || true'
            echo "Pipeline succeeded: images ${BACKEND_IMAGE}:${APP_VERSION} and ${FRONTEND_IMAGE}:${APP_VERSION} packaged."
        }
        failure {
            echo 'Pipeline failed - check the stage logs above.'
        }
    }
}
