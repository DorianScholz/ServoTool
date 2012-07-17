"""
====================
 PyS60RemoteControl
====================
http://pys60rc.sourceforge.net/
(c) 2007 Dorian Scholz
Released under the GNU General Public Licence
"""
import pprint

class Configuration:
    def __init__(self, conf_file_name):
        self.conf_file_name = conf_file_name
        self.conf = None

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def get(self, key, default=None):
        if not self.conf:
            self.load()
        if self.conf:
            if self.conf.has_key(key):
                return self.conf[key]
            else:
                self.set(key, default)
        return default

    def set(self, key, value):
        if not self.conf:
            self.load()
        self.conf[key] = value
        self.save()

    def update(self, dictonary):
        if not self.conf:
            self.load()
        self.conf.update(dictonary)
        self.save()

    def load(self):
        try:
            self.conf = eval(open(self.conf_file_name, 'U').read())
        except IOError:
            self.conf = {}
            print 'error opening file %s' % (self.conf_file_name)

    def save(self):
        try:
            pprint.pprint(self.conf, stream=open(self.conf_file_name, 'w'), indent=2)
        except IOError:
            print 'error opening file ' + self.conf_file_name
