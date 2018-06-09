
'''
this is a key-value store wrapper around redis.
'''
import redis
from os import environ
import json
from datetime import datetime
import logging
import dill as pickle

_redis_store = None

logger = logging.Logger(name='redisdb')
logger.setLevel(logging.INFO)

def conn():
    global _redis_store
    if not _redis_store: # establish a new connection.
        db_url = environ.get('TURK_DB')
        if db_url:
            (host, port) = db_url.split(':')
            port = int(port)
        else:
            host = 'localhost'
            port = 6379
        _redis_store = redis.StrictRedis(host=host, port=port, db=0, password='openai')
        logger.info('Connecting to database %s:%d', host, port)
    return _redis_store


def set_testing_mode():
    global _redis_store
    import fakeredis
    _redis_store = fakeredis.FakeStrictRedis()


def flush_db():
    conn().flushdb()


def loads(raw, default=None):
    if raw is not None:
        return pickle.loads(raw)
    return default


def dumps(obj):
    return pickle.dumps(obj)


class KeyValueStore(object):
    '''
    a simple model template for key-value stores.
    '''
    @staticmethod
    def scopes(pattern='*'):
        '''
        use pattern to match scopes
        '''
        return conn().keys(pattern)


    def __init__(self, scope_name=None):
        '''
        scope_name: scope of the key-value store.
        if scope_name is None, then it uses the entire redis db as key-value store.
        '''
        self.conn = conn()
        self.scope_name = scope_name


    def __getitem__(self, key):
        '''
        usage: store[key]
        return the value corresponding to the key in DB.
        '''
        if self.scope_name:
            raw = self.conn.hget(self.scope_name, key)
        else:
            raw = self.conn.get(key)
        return loads(raw)


    def get(self, key, default=None):
        '''
        usage: store.get(key, default=xxx)
        return the value if key is found, else return default.
        '''
        if key in self:
            return self[key]
        return default


    def __len__(self):
        if self.scope_name:
            return self.conn.hlen(self.scope_name)
        else:
            return self.conn.dbsize()


    def __contains__(self, key):
        if self.scope_name:
            raw = self.conn.hget(self.scope_name, key)
            return raw is not None
        else:
            return raw in self.conn


    def __setitem__(self, key, value):
        if self.scope_name:
            return self.conn.hset(self.scope_name, key, dumps(value))
        else:
            return self.conn.set(key, dumps(value))


    def remove(self, key):
        if self.scope_name:
            return self.conn.hdel(self.scope_name, key)
        else:
            return self.conn.delete(key)


    def update(self, dic):
        for key, value in dic.items():
            self[key] = value


    def mget(self, keys):
        return {k: self[k] for k in keys}


    def keys(self):
        if self.scope_name:
            return self.conn.hkeys(self.scope_name)
        else:
            return self.conn.keys()

    def dump(self, f):
        ''' serialize the database to file.
        '''
        kv = {}
        for key in self.keys():
            kv[key] = self[key]
        pickle.dump(kv, f)

    def load(self, f):
        kv = pickle.load(f)
        for (k, v) in kv.items():
            self[k] = v


class SortedList(object):
    '''
    a model for storing sorted list (increasing).
    '''
    def __init__(self, scope_name=None):
        self.conn = conn()
        self.scope_name = scope_name


    def append(self, item, score):
        self.conn.zadd(self.scope_name, score, dumps(item))


    def __len__(self):
        return self.conn.zcount(self.scope_name, -float('inf'), float('inf'))


    def __getslice__(self, i, j):
        load_all = lambda objs: [loads(obj) for obj in objs]
        trans = lambda num: len(self) - num if num < 0 else num
        i = trans(i)
        j = trans(j)
        if i == j:
            return []
        elif i < j:
            return load_all(self.conn.zrange(self.scope_name, i, j, desc=False))
        else:
            return list(reversed(load_all(self.conn.zrange(self.scope_name, j, i, desc=False))))
