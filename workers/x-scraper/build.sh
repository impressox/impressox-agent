docker build -t hiepht/cpx:x-scraper-$1 .
docker push hiepht/cpx:x-scraper-$1
docker rmi -f hiepht/cpx:x-scraper-$1