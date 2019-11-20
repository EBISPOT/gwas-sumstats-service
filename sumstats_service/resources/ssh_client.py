import paramiko

class SSHClient():
    def __init__(self, host, username):
        self.host = host
        self.username = username
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.connect(self.host, self.username)

    def exec_command(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return (stdin, stdout, stderr)

    def submit_job(self, command, mem=1000, queue='production-rh74'):
        submit_command = 'bsub -q {q} -M {mem} -R "rusage[mem={mem}]" \'{com}\''.format(q=queue, mem=mem, com=command)
        return self.exec_command(submit_command)

    def get_job_status(jobid):
        poll_command = 'bjobs -o "STAT" -noheader {}'.format(jobid)
        return self.exec_command(poll_command)
        

