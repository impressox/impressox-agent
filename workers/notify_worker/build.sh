#!/bin/bash
# Build the Docker image
docker build -t hiepht/cpx:notify-worker-$1 -f Dockerfile .
docker push hiepht/cpx:notify-worker-$1
docker rmi -f hiepht/cpx:notify-worker-$1