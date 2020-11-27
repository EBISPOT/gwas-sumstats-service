//run with:
///nextflow run test_singularity.nf -with-singularity ebispot/gwas-sumstats-service:latest

params.storepath = 'data/test1234'
params.cid = 'test1234'
params.payload = 'data/test1234/payload.json'


process foo {

  containerOptions "--bind $params.storepath"

  output:
  stdout receiver

  """
  ls $params.storepath
  validate-payload -metadata -cid $params.cid -payload $params.payload -storepath $params.storepath -out $params.storepath/$params.cid/meta-val.json
  """

}

receiver.view { it }
