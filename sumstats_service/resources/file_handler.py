import os
import urllib.request
import config


class SumStatFile:
    def __init__(self, file_path=None, callback_id=None):
        self.file_path = file_path
        self.callback_id = callback_id
        self.store_path = os.path.join(config.STORAGE_PATH, self.callback_id)


    def make_parent_dir(self):
        # make dir if not
        try:
            os.makedirs(self.store_path)
        except FileExistsError:
            pass

    def retrieve(self):
        self.make_parent_dir()
        try:
            urllib.request.urlretrieve(self.file_path, self.store_path)
            return True
        except (ValueError, urllib.error.HTTPError):
            return False

