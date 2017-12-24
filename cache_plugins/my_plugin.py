from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    cache: my_cache
    author: Igor Lakhtenkov (igor_lakhtenkov@epam.com)
    short_description: Use Mongo DB for cache
    description:
        - This cache module stores host facts in MongoDB in JSON format.
    version_added: "1.0"
    requirements:
      - pymongo python lib
    options could be defined in ansible.cfg:
      fact_caching_connection:
        description:
          - A colon separated string of connection information for MongoDB.
        required: True
        example: localhost:27017:db_name:collection_name
      fact_caching_timeout:
        required: False
        default: 86400 (24h)
        description: Expiration timeout for the cache plugin data
'''

import json
import time
from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.plugins.cache import BaseCacheModule

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

try:
    import pymongo
except ImportError:
    raise AnsibleError ("Mongodb python module is required for the mongodb cache, 'pip install pymongo'")

class CacheModule(BaseCacheModule):

    def __init__(self, *args, **kwargs):
        self.plugin_name = self.__module__.split('.')[-1]
        self._timeout = float(C.CACHE_PLUGIN_TIMEOUT)
        self._connection = C.CACHE_PLUGIN_CONNECTION.split(':')
        self._cache = {}
        client = pymongo.MongoClient(self._connection[0], int(self._connection[1]))
        self._db = client[self._connection[2]]
        self._collection = self._db[self._connection[3]]

    def set(self, key, value):
        value2 = json.dumps(value)
        if self._collection.find_one({"key": key}):
            self._collection.update({"key": key},{"key": key, "value": value2, "time": time.time()})
        else:
            self._collection.insert_one({"key": key, "value": value2, "time": time.time()})
        self._cache[key] = value
    
    def get(self, key):
        if key not in self._cache:
            if self.has_expired(key) or key == "":
                raise KeyError
            try:
                value = self._collection.find_one({"key": key})['value']
                if value is None:
                    self.delete(key)
                    raise KeyError
                self._cache[key] = json.loads(value)
            except ValueError as e:
                display.warning("error in '%s' cache plugin while trying to read from db %s. Erasing and failing." % (self.plugin_name, self._connection))
                self.delete(key)
                raise AnsibleError("The cache file was corrupt, or did not otherwise contain valid data. "
                                   "It has been removed, so you can re-run your command now.")
            except Exception as e:
                raise AnsibleError("Error while decoding the cache file")

        return self._cache.get(key)
            
 
    def keys(self):
        keys = []
        for k in self._collection.find():
            if not self.has_expired(k["key"]):
                keys.append(k)
        return keys

    def contains(self, key):
        if key in self._cache:
            return True
        if self.has_expired(key):
            return False
        if self._collection.find_one({"key": key}) is not None:
            return True

    def has_expired(self, key):

        if self._timeout == 0:
            return False
        try:
            key_time =  self._collection.find_one({"key": key})['time']  
        except:
            return False
        if float(time.time()) - key_time <= self._timeout:
            return False

        if key in self._cache:
            del self._cache[key]
        return True

    def delete(self, key):
        del self._cache[key]
        self._collection.remove({'key': key})

    def flush(self):
        self._cache = {}
        for key in self.keys():
            self.delete(key)

    def copy(self):
        ret = dict()
        for key in self.keys():
            ret[key] = self.get(key)
        return ret

    def __getstate__(self):
        return self.copy()

    def __setstate__(self, data):
        self._cache = data
    
