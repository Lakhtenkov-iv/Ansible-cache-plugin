#!/bin/bash
echo "--------------Starting mongodb container:--------------"
docker-compose up -d
echo "--------------Running ansible--------------------------"
ansible-playbook -i inventory hello.yml
echo "--------------Check information in DB:-----------------"
docker exec -it mongo mongo facts --eval "db.hosts.find().pretty()"
echo -n "Do you want to stop mongodb container [Yes|No]: "
read answer
if [ $answer == 'Yes' ]
then
  docker-compose down
fi
