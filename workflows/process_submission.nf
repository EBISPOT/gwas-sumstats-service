nextflow.enable.dsl=2
//run with:
//nextflow run validate_submission.nf --payload test/data/test1234/payload.json --storepath test/data/ -w test/data/test1234/work --ftpServer <> --ftpUser <> --ftpPWD <> --cid test1234

// Path to store files for fast accesss
params.storePath = ''
params.cid = ''
params.payload = ''
params.ftpServer = ''
params.ftpPWD = ''
params.ftpUser = ''
params.minrows = '10'
params.forcevalid = 'False'
params.zerop = 'False'

// path to do the work
params.validatedPath = 'test_depo_validated'

// path where files are deposited by users
params.depo_data = ''


// parse json payload
import groovy.json.JsonSlurper
def jsonSlurper = new JsonSlurper()
payload = jsonSlurper.parse(new File("$params.payload"))

// create ids channel from study ids
entries = []
payload["requestEntries"].each { it -> entries.add( it.id ) }
ids = Channel.from(entries)


process get_submitted_files {

  queue 'datamover'
  containerOptions "--bind $params.storePath"
  containerOptions "--bind $params.depo_data"
  memory { 2.GB }
  time { 2.hour * task.attempt }
  maxRetries 5
  errorStrategy { task.exitStatus in 130..255 ? 'retry' : 'terminate' }

  input:
  val id

  output:
  val id


  """
  validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storePath -validated_path $params.validatedPath -depo_path $params.depo_data --copy_only True -out "${id}".json
  """
}

process validate_study {

  queue 'short'
  containerOptions "--bind $params.storePath"
  memory { 4.GB * task.attempt }
  time { 2.hour * task.attempt }
  maxRetries 5  
  errorStrategy { task.exitStatus in 130..255 ? 'retry' : 'terminate' }

  input:
  val id
  
  output:
  stdout

  """
  validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storePath -minrows $params.minrows -zero_p $params.zerop -forcevalid $params.forcevalid -out "${id}".json -validated_path $params.validatedPath
  """

}

workflow {
    ids = channel.from(entries)
    get_submitted_files(ids)
    validate_study(get_submitted_files.out)
}


