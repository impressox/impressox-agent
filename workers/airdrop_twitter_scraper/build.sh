#!/bin/bash
# Build the Docker image
docker build -t hiepht/cpx:airdrop-twitter-scraper-$1 -f Dockerfile .
docker push hiepht/cpx:airdrop-twitter-scraper-$1
docker rmi -f hiepht/cpx:airdrop-twitter-scraper-$1