# this script launches annotator containers on devboxes.
for PORT_OFFSET in $@;
do
  cd ../world-of-bits && make turk ENV=$ENV TURK_DB=10.6.21.209:6380 PORT_OFFSET=$PORT_OFFSET
  cd ../annotator && make run PORT_OFFSET=$PORT_OFFSET
done;
