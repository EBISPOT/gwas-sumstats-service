//run with:
///nextflow run test_singularity.nf -with-singularity ebispot/gwas-sumstats-service:latest

params.storepath = 'data/test1234'
params.cid = 'test1234'
params.payload = 'data/test1234/payload.json'
params.ftpServer = ''
params.ftpPWD = ''
params.ftpUser = ''


// parse json payload
import groovy.json.JsonSlurper
def jsonSlurper = new JsonSlurper()
payload = jsonSlurper.parse(new File("$params.payload"))
// create ids channel from study ids
entries = []
payload["requestEntries"].each { it -> entries.add( it.id ) }
ids = Channel.from(entries)


process validate_study {

  containerOptions "--bind $params.storepath"

  input:
  val(id) from ids
  
  output:
  stdout into result


  shell:
  '''
  metadata=$(cat !{params.payload} | jq '.requestEntries[] | select(.id =="!{id}")')
  id="!{id}"
  validate-study -cid !{params.cid} -id "$id" -payload !{params.payload} -storepath !{params.storepath} -ftpserver !{params.ftpServer} -ftpuser !{params.ftpUser} -ftppass !{params.ftpPWD}
  '''

}


result.view { it }
