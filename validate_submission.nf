//run with:
//nextflow run validate_submission.nf --payload test/data/test1234/payload.json --storepath test/data/ -w test/data/test1234/work --ftpServer <> --ftpUser <> --ftpPWD <> --cid test1234

params.storePath = ''
params.cid = ''
params.payload = ''
params.ftpServer = ''
params.ftpPWD = ''
params.ftpUser = ''
params.minrows = '10'
params.forcevalid = 'False'
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
  time { 5.hour * task.attempt }
  maxRetries 5
  errorStrategy { task.exitStatus in 2..140 ? 'retry' : 'terminate' }
  publishDir "$params.storePath", mode: 'copy'

  input:
  val(id) from ids

  output:
  file "${id}.json" into validated

  """
  validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storePath -ftpserver $params.ftpServer -ftpuser $params.ftpUser -ftppass $params.ftpPWD -minrows $params.minrows -forcevalid $params.forcevalid -out "${id}".json -validated_path $params.validatedPath
  """

}

process clean_up {

  containerOptions "--bind $params.storePath"
  memory { 2.GB * task.attempt }
  time { 5.hour * task.attempt }
  maxRetries 5
  errorStrategy { task.exitStatus in 2..140 ? 'retry' : 'terminate' }

  input:
  file "*.json" from validated.collect()

  output:
  stdout into result

  """
  payload -cid $params.cid -payload $params.payload -storepath $params.storePath -ftpserver $params.ftpServer -ftpuser $params.ftpUser -ftppass $params.ftpPWD
  """

}

result.view { it }
