"""
# read in xls/csv
# using a schema convert this to yaml
# which schema?

# Where does the schema live?
# - validator?
# - standard?
# - here?
"""

import argparse
import pandas as pd
import yaml
import config
import logging

logging.basicConfig(level=logging.ERROR, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)

class metadataConverter():
    def __init__(self,
                 accession_id,
                 md5sum,
                 in_file,
                 out_file,
                 in_type,
                 out_type,
                 schema,
                 data_file_ext):
        self.accession_id = accession_id
        self.md5sum = md5sum
        self.in_file = in_file
        self.out_file = out_file
        self.in_type = in_type
        self.out_type = out_type
        self.schema = schema
        self.data_file_ext = data_file_ext
        self.metadata = None
        self.formatted_metadata = None
        self.header_mappings = config.SUBMISSION_TEMPLATE_HEADER_MAP
        self.template_version = None

    def read_metadata_from_file(self):
        if self.in_type == "gwas_sub_xls":
            self.metadata = self.read_excel_file()
        else:
            logger.error("Don't recognise that input type")

    def read_excel_file(self):
        """
        read all the sheets store in separate metadata dataframes
        store the metadata for the accession ID in self.metadata
        """
        study_df = pd.read_excel(self.in_file, sheet_name='study',
                                 skiprows=[0, 2, 3])
        sample_df = pd.read_excel(self.in_file, sheet_name='sample',
                                  skiprows=[0, 2, 3])
        meta_df = pd.read_excel(self.in_file, sheet_name='meta')
        self.get_template_version(meta_df=meta_df)
        merged_df = pd.merge(study_df, sample_df, on="Study tag")
        return merged_df
    
    
    def get_template_version(self, meta_df):
        try:
            self.template_version = float(meta_df[meta_df['Key'] == 'schemaVersion']['Value'].values[0])
            logger.debug(self.template_version)
        except IndexError:
            logger.warning('Cannot determine template version, assuming latest')

    def write_metadata_to_file(self):
        if self.out_type == "ssf_yaml":
            with open(self.out_file, "w") as f:
                yaml.dump(self.formatted_metadata, f, encoding='utf-8')
        else:
            logger.error("Output type not recognised")

    def format_metadata(self):
        if self.template_version < 1.8:
            self.header_mappings = config.SUBMISSION_TEMPLATE_HEADER_MAP_pre1_8
        meta_dict = {'summaryStatisticsMetadata':{}}
        if self.out_type == "ssf_yaml":
            record_meta = self.get_record_from_metadata()[0]
            schema = self.read_schema()
            schema_fields = {key: value for key, value in schema['mapping']['summaryStatisticsMetadata']['mapping'].items()}
            for field, value in record_meta.items():
                if field in self.header_mappings:
                    key = self.header_mappings[field]
                    if key in schema_fields:
                        dtype = schema_fields[key]['type']
                        # format list type fields
                        if dtype == 'seq':
                            seq = [v for v in value.split("|")]
                            vdtype = schema_fields[key]['sequence']['type']
                            formatted_value = [self.coerce_yaml_dtype(value=v, dtype=vdtype) for v in seq]
                        # format the other types of fields
                        else:
                            formatted_value = self.coerce_yaml_dtype(value=value, dtype=dtype)
                        meta_dict['summaryStatisticsMetadata'][key] = formatted_value
        else:
            logger.error("Output type not recognised")
        return meta_dict

    def coerce_yaml_dtype(self, value, dtype):
        convert_to_type = str
        yaml_dtypes = config.YAML_DTYPES
        if dtype in yaml_dtypes:
            convert_to_type = yaml_dtypes[dtype]
            if convert_to_type == str:
                cleaned_str = self.sanitise_str(value)
                return cleaned_str
        return convert_to_type(value)

    @staticmethod
    def sanitise_str(string):
        encoded_str = string.encode(encoding="ascii", errors="ignore")
        decoded_str = encoded_str.decode()
        stripped = decoded_str.strip()
        no_newlines = stripped.replace('\n','')
        return no_newlines

    def get_record_from_metadata(self):
        key_field = 'md5 sum'
        key = self.md5sum
        record = self.metadata[self.metadata[key_field] == key]
        if len(record) == 0:
            logger.error("key {} not found in metadata".format(key))
        elif len(record) > 1:
            logger.error("more than 1 record found in metadata for key {}".format(key))
        else:
            # remove fields without values 
            record.dropna(axis='columns', inplace=True)
            return record.to_dict(orient='records')

    def read_schema(self):
        with open(self.schema, 'r') as f:
            schema = yaml.safe_load(f)
        return schema

    def extend_metadata(self):
        self.add_id_to_meta()
        self.add_data_file_name_to_meta()
        self.add_md5_to_meta()
        self.add_defaults_to_meta()
        self.add_gwas_cat_link()

    def add_data_file_name_to_meta(self):
        if not str(self.data_file_ext).startswith("."):
            self.data_file_ext = "." + self.data_file_ext
        data_file_name = self.accession_id + self.data_file_ext
        self.formatted_metadata['summaryStatisticsMetadata']['dataFileName'] = data_file_name

    def add_id_to_meta(self):
        self.formatted_metadata['summaryStatisticsMetadata']['GWASID'] = self.accession_id

    def add_md5_to_meta(self):
        self.formatted_metadata['summaryStatisticsMetadata']['dataFileMd5sum'] = self.md5sum

    def add_defaults_to_meta(self):
        self.formatted_metadata['summaryStatisticsMetadata']['fileType'] = config.SUMSTATS_FILE_TYPE

    def add_gwas_cat_link(self):
        self.formatted_metadata['summaryStatisticsMetadata']['GWASCatalogAPI'] = config.GWAS_CATALOG_REST_API_STUDY_URL + self.accession_id

    def convert_to_outfile(self):
        self.read_metadata_from_file()
        self.formatted_metadata = self.format_metadata()
        self.extend_metadata()
        if self.formatted_metadata:
            logger.debug("writing to file")
            self.write_metadata_to_file()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-md5sum", help='md5sum of the submitted sumstats file, which is used as a key for the metadata', required=True)
    argparser.add_argument("-id", help='GWAS accession id', required=True)
    argparser.add_argument("-in_file", help='File to read in', required=True)
    argparser.add_argument("-out_file", help='File to write metadata to', required=True)
    argparser.add_argument("-in_type", help='Type of file being read', default='gwas_sub_xls')
    argparser.add_argument("-out_type", help='Type of file to convert to', default='ssf_yaml')
    argparser.add_argument("-schema", help='Schema for output', required=True)
    argparser.add_argument("-file_ext", help='Data file extension', required=True)
    args = argparser.parse_args()

    """
    md5sum is used as a key to pull out the relevant information from the metadata file. 
    TODO: add in the accession ID, md5 of the final compressed file, defaults, 
    """
    md5sum = args.md5sum
    accession_id = args.id
    in_file = args.in_file
    out_file = args.out_file
    in_type = args.in_type
    out_type = args.out_type
    schema = args.schema
    data_file_ext = args.file_ext

    converter = metadataConverter(accession_id=accession_id,
                                  md5sum=md5sum,
                                  in_file=in_file,
                                  out_file=out_file,
                                  in_type=in_type,
                                  out_type=out_type,
                                  schema=schema,
                                  data_file_ext=data_file_ext
                                  )
    converter.convert_to_outfile()


if __name__ == '__main__':
    main()
