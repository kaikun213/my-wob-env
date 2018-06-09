for id in $(docker ps | awk '{if($2 == "'$1'") {print $1}}'); do docker rm -f $id; done
