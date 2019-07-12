import sqlite3


class sqlClient():
    def __init__(self, database):
        self.database = database
        self.conn = self.create_conn()
        self.cur = self.conn.cursor()

    def create_conn(self):
        try:
            conn = sqlite3.connect(self.database)
            return conn
        except NameError as e:
            print(e)
        return None

    def insert_study(self, data):
        self.cur.execute("insert or ignore into studies(studyID, callbackID, pmID, filePath, md5, assembly) values (?,?,?,?,?,?)", data)

    def get_study_metadata(self, study):
        data = []
        for row in self.cur.execute("select * from studies where studyID =?", (study,)):
            data.append(row[0])
        if data:
            return data
        else:
            return False


    

