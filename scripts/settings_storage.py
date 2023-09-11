import json
from scripts import constant
import os

class _SettingsStorage:

    def __init__(self,):
        self.json_decoded = json.loads("{}")

        # check if not exist create empty file
        if not os.path.isfile(constant.settingsStorageJsonPath) or not os.access(constant.settingsStorageJsonPath, os.R_OK):
            with open(constant.settingsStorageJsonPath, 'w') as json_file:
                json_file.write(json.dumps({}))
                json_file.close()


        with open(constant.settingsStorageJsonPath) as json_file:
            self.json_decoded = json.loads(json_file.read())
            json_file.close()

    def save(self):
        with open(constant.settingsStorageJsonPath, 'w') as json_file:
            json_file.write(json.dumps(self.json_decoded))
            #json.dump(self.json_decoded, json_file)
            json_file.close()
            
    
    def get(self, key):
        if key in self.json_decoded:
            return self.json_decoded[key]
        return None
    
    def set(self, key, val):
        self.json_decoded[key] = val



settingsStorage = _SettingsStorage()