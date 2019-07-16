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

    """ insert statements """

    def insert_new_study(self, data):
        self.cur.execute("""
                         INSERT OR IGNORE INTO studies(
                         studyID, callbackID, pmID, 
                         filePath, md5, assembly)
                         VALUES (?,?,?,?,?,?)
                         """, 
                         data)
        self.commit()

    """ select statements """
    
    def get_study_metadata(self, study):
        data = []
        for row in self.cur.execute("select * from studies where studyID =?", (study,)):
            data.append(row)
        if data:
            return data
        return None

    def get_study_count(self):
        count = []
        for row in self.cur.execute("select count(studyID) from studies"):
            count.append(row[0])
        count = count[0]
        return count

    def get_data_from_callback_id(self, callback_id):
        data = []
        for row in self.cur.execute("select * from studies where callbackID =?", (callback_id,)):
            data.append(row)
        if data:
            return data
        return None

    """ OTHER STATEMENTS """

    def commit(self):
        self.cur.execute("COMMIT")


    

