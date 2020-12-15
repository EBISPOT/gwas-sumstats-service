//run with:
//nextflow run validate_submission.nf --payload test/data/test1234/payload.json --storepath test/data/ -w test/data/test1234/work --ftpServer <> --ftpUser <> --ftpPWD <> --cid test1234

params.storePath = ''
params.cid = ''
params.payload = ''
params.ftpServer = ''
params.ftpPWD = ''
params.ftpUser = ''
params.minrows = '10'
params.validatedPath = 'test_depo_validated'


// parse json payload
import groovy.json.JsonSlurper
def jsonSlurper = new JsonSlurper()
payload = jsonSlurper.parse(new File("$params.payload"))

// create ids channel from study ids
entries = []
payload["requestEntries"].each { it -> entries.add( it.id ) }
ids = Channel.from(entries)


process validate_study {

  containerOptions "--bind $params.storePath"
  memory { 2.GB * task.attempt }
  time { 1.hour * task.attempt }
  maxRetries 5  
  errorStrategy { task.exitStatus in 2..140 ? 'retry' : 'terminate' }

  input:
  val(id) from ids
  
  output:
  stdout into result


  """
  validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storePath -ftpserver $params.ftpServer -ftpuser $params.ftpUser -ftppass $params.ftpPWD -minrows $params.minrows -out "${id}".json -validated_path $params.validatedPath
  """

}


result.view { it }
