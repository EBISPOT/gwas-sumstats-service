import os
import urllib.request
import config


class SumStatFile:
    def __init__(self, file_path=None, callback_id=None, study_id=None):
        self.file_path = file_path
        self.callback_id = callback_id
        self.study_id = study_id
        if callback_id:
            self.parent_path = os.path.join(config.STORAGE_PATH, self.callback_id)
            if study_id: 
                self.store_path = os.path.join(self.parent_path, self.study_id)


    def make_parent_dir(self):
        try:
            os.makedirs(self.parent_path)
        except FileExistsError:
            pass

    def retrieve(self):
        self.make_parent_dir()
        print(self.store_path)
        try:
            urllib.request.urlretrieve(self.file_path, self.store_path)
            return True
        except (ValueError, urllib.error.HTTPError) as e:
            print(e)
            return False

