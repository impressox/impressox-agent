#!/bin/bash
# Build the Docker image
docker build -t hiepht/cpx:rag-processor-$1 -f Dockerfile .
docker push hiepht/cpx:rag-processor-$1
docker rmi -f hiepht/cpx:rag-processor-$1