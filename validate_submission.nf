//run with:
///nextflow run test_singularity.nf -with-singularity ebispot/gwas-sumstats-service:latest --payload /path/to/payload.json --storepath /path/to/storepath -w /path/to/workpath

params.storepath = 'data/test1234'
params.cid = 'test1234'
params.payload = 'data/test1234/payload.json'
params.ftpServer = ''
params.ftpPWD = ''
params.ftpUser = ''

payload_id = Channel.from(params.cid)


// create json out file
//import groovy.json.JsonOutput
//def data = [
//      callbackID: "$params.cid",
//      validationList: []
//      ]
//
//def json_str = JsonOutput.toJson(data)
//def json_beauty = JsonOutput.prettyPrint(json_str)
//File file = new File("$params.storepath", "$params.cid", "validate.json")
//file.write(json_beauty)

// parse json payload
import groovy.json.JsonSlurper
def jsonSlurper = new JsonSlurper()
payload = jsonSlurper.parse(new File("$params.payload"))

// create ids channel from study ids
entries = []
payload["requestEntries"].each { it -> entries.add( it.id ) }
ids = Channel.from(entries)


process validate_study {

  afterScript 'echo "hello"'
  containerOptions "--bind $params.storepath"

  input:
  val(id) from ids
  
  output:
  stdout into result
  file "${id}.json" into json_out


  """
  validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storepath -ftpserver $params.ftpServer -ftpuser $params.ftpUser -ftppass $params.ftpPWD -minrows 10 -out "$id".json
  """

}


result.view { it }
