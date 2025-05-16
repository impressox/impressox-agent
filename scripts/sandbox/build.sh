#!/bin/bash

# Build the Docker image
docker build -t hiepht/cpx:python-sandbox-img -f Dockerfile .
# docker push hiepht/cpx:market-monitor-$1
# docker rmi -f hiepht/cpx:market-monitor-$1