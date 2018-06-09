# deprecated: now HTTP cache uses redis for
# database utils for server.
import sqlite3 as sql
import base64
import json
import os
from datetime import datetime
import dill as pickle


class DBConn(object):
    def __init__(self, db_path):
        self.db_path = db_path

    def __enter__(self):
        conn = sql.connect(self.db_path)
        conn.row_factory = sql.Row
        self.conn = conn
        return conn

    def __exit__(self, type, value, traceback):
        self.conn.commit()
        self.conn.close()


class KeyValueStore(object):
    '''
    a simple model template for key-value stores.
    '''
    def __init__(self, db_path, db_name, key_type='TEXT'):
        '''
        db_name: name of the key-value store database.
        key_type: the type of primary key: TEXT, INTEGER, REAL, BLOB
        the value_type will be BLOB.
        '''
        self.db_path = db_path
        self.db_name = db_name
        self.key_type = key_type

        with DBConn(db_path) as conn:
            conn.execute('''
                    CREATE TABLE IF NOT EXISTS %(db_name)s
                    (k %(key_type)s PRIMARY KEY,
                     v BLOB)
                    ''' %
                    dict(db_name=db_name, key_type=key_type))


    def __getitem__(self, key):
        '''
        usage: store[key]
        return the value corresponding to the key in DB.
        '''
        with DBConn(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                    SELECT v FROM %(db_name)s WHERE k=:k
                    ''' % dict(db_name=self.db_name),
                    dict(k=key)
                )
            row = cursor.fetchone()
            if row:
                return pickle.loads(row['v'])


    def __contains__(self, key):
        return self[key] is not None


    def __setitem__(self, key, value):
        with DBConn(self.db_path) as conn:
            cursor = conn.cursor()
            if key in self:
                cursor.execute('''
                        UPDATE %(db_name)s
                        SET v=:v
                        WHERE k=:k
                        ''' % dict(db_name=self.db_name),
                        dict(k=key, v=pickle.dumps(value))
                    )
            else:
                cursor.execute('''
                        INSERT INTO %(db_name)s(k, v)
                        VALUES (:k, :v)
                        ''' % dict(db_name=self.db_name),
                        dict(k=key, v=pickle.dumps(value))
                    )

    def __len__(self):
        with DBConn(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT (SELECT COUNT() from %(db_name)s) as count'''
                        % dict(db_name=self.db_name))
            row = cursor.fetchone()
            return int(row['count'])

    def keys(self):
        with DBConn(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                    SELECT k FROM %(db_name)s
                    ''' % dict(db_name=self.db_name)
                )
            rows = cursor.fetchall()
            return [row['k'] for row in rows]


    def remove(self, key):
        if key not in self:
            return
        with DBConn(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                    DELETE FROM %(db_name)s
                    WHERE k=:k
                ''' % dict(db_name=self.db_name),
                dict(k=key)
            )

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

