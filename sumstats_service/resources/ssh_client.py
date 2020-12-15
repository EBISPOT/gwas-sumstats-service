import paramiko
import re
import config
import os


class SSHClient():
    def __init__(self, host, username):
        self.host = host
        self.username = username
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.connect(self.host, username=self.username)

    def exec_command(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return (stdin, stdout, stderr)

    def submit_job(self, command, mem=1000, queue='production-rh74'):
        submit_command = 'bsub -q {q} -M {mem} -R "rusage[mem={mem}]" \'{com}\''.format(q=queue, mem=mem, com=command)
        return self.exec_command(submit_command)

    def get_job_status(self, jobid):
        poll_command = 'bjobs -o "STAT" -noheader {}'.format(jobid)
        stdin, stdout, stderr = self.exec_command(poll_command)
        status = stdout.read().decode().rstrip()
        return status

    def write_data_to_file(self, data, filepath):
        sftp = self.client.open_sftp()
        with sftp.open(filepath, "w") as f:
            f.write(data)

    def mkdir(self, dirname):
        sftp = self.client.open_sftp()
        try:
            sftp.mkdir(dirname)
        except IOError:
            pass

    def rm(self, path):
        if config.STORAGE_PATH not in path:
            # shouldn't be removing files elsewhere
            pass
        else:
            sftp = self.client.open_sftp()
            files = sftp.listdir(path)
            for f in files:
                filepath = os.path.join(path, f)
                try:
                    sftp.remove(filepath)
                except IOError:
                    self.rm(filepath)
            sftp.rmdir(path)


    @staticmethod
    def parse_jobid(stdout):
        stdout_str =  stdout.read().decode()
        if "Job" in stdout_str:
            return re.search(r"Job <([0-9]+)>.*", stdout_str).group(1)
        else:
            return None

    def get_exit_reason(self):
        pass

    def get_file_content(self, file_path):
        command = 'cat {}'.format(file_path)
        stdin, stdout, stderr = self.exec_command(command)
        content = stdout.read().decode().rstrip()
        return content

    def close_connection(self):
        self.client.close()
        
