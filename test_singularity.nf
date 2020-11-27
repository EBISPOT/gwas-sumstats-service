//run with:
///nextflow run test_singularity.nf -with-singularity ebispot/gwas-sumstats-service:latest

params.storepath = ''


process foo {

  containerOptions "--bind $params.storepath"

  output:
  stdout receiver

  """
  ls $params.storepath
  validate-payload --help
  """

}

receiver.view { it }
