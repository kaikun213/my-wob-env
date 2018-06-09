#!/usr/bin/env python
# dump entries in the realwob database to file.
# this is useful if we want to create a "dataset" for a particular task, for
#    exmaple, BookFlight.
import sys
import realwob.db.sqlite as sqlite
import realwob.db.redisdb as redisdb

if len(sys.argv) < 5:
    print('Usage: ./bin/realwob_db.py [command] [db_type] [db_path] [io_path]')
    exit(1)

command = sys.argv[1]
db_type = sys.argv[2]
db_path = sys.argv[3]
io_path = sys.argv[4]

if db_type == 'sqlite':
    kv_store = sqlite.KeyValueStore(db_path, 'main')
elif db_type == 'redis':
    kv_store = redisdb.KeyValueStore(scope_name=db_path)
else:
    raise ValueError('unrecognized database type {}'.format(db_type))

if command == 'dump':
    with open(io_path, 'wb') as f:
        kv_store.dump(f)
elif command == 'load':
    with open(io_path, 'rb') as f:
        kv_store.load(f)
else:
    raise ValueError('unrecognized command {}'.format(command))
