nextflow.enable.dsl=2

// Parameters with default values
params.storePath = params.storePath ?: ''
params.cid = params.cid ?: ''
params.payload = params.payload ?: ''
params.ftpServer = params.ftpServer ?: ''
params.ftpPWD = params.ftpPWD ?: ''
params.ftpUser = params.ftpUser ?: ''
params.minrows = params.minrows ?: '10'
params.forcevalid = params.forcevalid ?: 'False'
params.validatedPath = params.validatedPath ?: 'test_depo_validated'
params.depo_data = params.depo_data ?: ''

// Parse JSON payload
import groovy.json.JsonSlurper
def jsonSlurper = new JsonSlurper()
payload = jsonSlurper.parse(new File("$params.payload"))

// Create IDs and analysisSoftware channel from study IDs
entries = []
softwareFlags = []
payload["requestEntries"].each { 
    entries.add(it.id)
    softwareFlags.add(it.analysisSoftware ? 'True' : 'False')
}
ids = Channel.from(entries)
softwareFlagsChannel = Channel.from(softwareFlags)

process get_submitted_files {
    queue 'datamover'
    containerOptions "--bind $params.storePath"
    containerOptions "--bind $params.depo_data"
    memory { 4.GB }
    time { 4.hour * task.attempt }
    maxRetries 5
    errorStrategy { task.exitStatus in 130..255 ? 'retry' : 'terminate' }

    input:
    val id
    val softwareFlag

    output:
    tuple val(id), val(softwareFlag)

    script:
    """
    validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storePath -validated_path $params.validatedPath -depo_path $params.depo_data --copy_only True -out "${id}.json"
    """
}

process validate_study {
    queue 'short'
    containerOptions "--bind $params.storePath"
    memory { 8.GB * task.attempt }
    time { 4.hour * task.attempt }
    maxRetries 5  
    errorStrategy { task.exitStatus in 130..255 ? 'retry' : 'terminate' }

    input:
    tuple val(id), val(softwareFlag)
    
    output:
    stdout

    script:
    """
    validate-study -cid $params.cid -id $id -payload $params.payload -storepath $params.storePath -minrows $params.minrows -zero_p $softwareFlag -forcevalid $params.forcevalid -out "${id}.json" -validated_path $params.validatedPath
    """
}

workflow {
    get_submitted_files(ids, softwareFlagsChannel) | validate_study
}
