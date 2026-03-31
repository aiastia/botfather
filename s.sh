git checkout .
git pull 
docker-compose -f docker-compose.webhook.yml down
docker-compose -f docker-compose.webhook.yml up -d --build
