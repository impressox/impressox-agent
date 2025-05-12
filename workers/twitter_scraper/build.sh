#!/bin/bash
# Build the Docker image
docker build -t hiepht/cpx:twitter-scraper-$1 -f Dockerfile .
docker push hiepht/cpx:twitter-scraper-$1
docker rmi -f hiepht/cpx:twitter-scraper-$1