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

    # insert statements

    def insert_new_study(self, data):
        self.cur.execute("""
                         INSERT OR IGNORE INTO studies(
                         studyID, callbackID, pmID, 
                         filePath, md5, assembly)
                         VALUES (?,?,?,?,?,?)
                         """,
                         data)
        self.commit()

    # update statements

    def update_retrieved_status(self, study, status):
        study_status = status, study
        self.cur.execute("UPDATE studies SET retrieved = ? WHERE studyID =?", (study_status))
        self.commit()

    def update_data_valid_status(self, study, status):
        study_status = status, study
        self.cur.execute("UPDATE studies SET dataValid = ? WHERE studyID =?", (study_status))
        self.commit()

    # select statements

    def get_study_metadata(self, study):
        self.cur.execute("select * from studies where studyID =?", (study,))
        data = self.cur.fetchone()
        return data

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
        return data if data else None


    # OTHER STATEMENTS

    def commit(self):
        self.cur.execute("COMMIT")
