import argparse
import pandas as pd
import yaml
import json
import munch
from sumstats_service import config
from collections import defaultdict
import logging
from sumstats_service.resources.utils import download_with_requests
from sumstats_service.models.metadata import SumStatsMetadata


logging.basicConfig(level=logging.DEBUG, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


class MetadataConverter:
    HEADER_MAPPINGS = config.SUBMISSION_TEMPLATE_HEADER_MAP
    def __init__(self,
                 accession_id,
                 md5sum,
                 in_file,
                 out_file,
                 schema,
                 data_file,
                 in_type='gwas_sub_xls',
                 out_type='ssf_yaml'):
        self._accession_id = accession_id
        self._md5sum = md5sum
        self._in_file = in_file
        self._out_file = out_file
        self._in_type = in_type
        self._out_type = out_type
        self._schema_file = schema
        self._data_file_name = data_file
        self._metadata = None
        self._formatted_metadata = None
        self._template_version = None
        self._study_sheet = None
        self._sample_sheet = None
        self._study_record = {}
        self._sample_records = {'samples': []}
        self._schema_obj = None

    def convert_to_outfile(self):
        self._read_schema()
        self._read_metadata()
        self._study_record = self._get_study_record()
        self._get_sample_metadata()
        self._formatted_metadata = self._format_metadata(self._study_record,
                                                         self._sample_records)
        self.__extend_metadata()
        if self._formatted_metadata:
            logger.debug("writing to file")
            self._write_metadata_to_file()

    def _get_study_record(self):
        key = 'md5 sum'
        records = self._get_record_from_df(df=self._study_sheet,
                                           key=key,
                                           value=self._md5sum)
        if len(records) > 1:
            raise ValueError(f"more than 1 record found in metadata for key {key}")
        else:
            # remove fields without values
            records.dropna(axis='columns', inplace=True)
            return records

    def _get_sample_metadata(self):
        if self._sample_sheet is None:
            self._sample_records = self._get_sample_metadata_from_gwas_api()
        else:
            self._sample_records = self._get_sample_records()

    def _get_sample_records(self):
        study_tag_key = 'Study tag'
        if self._sample_sheet is not None:
            study_tag = self._study_record[study_tag_key][0]
            sample_records = self._get_record_from_df(df=self._sample_sheet,
                                                      key=study_tag_key,
                                                      value=study_tag)
            filtered_samples = self._get_record_from_df(df=sample_records,
                                                        key='Stage',
                                                        value='discovery')
            filtered_samples.dropna(axis='columns', inplace=True)
            return {'samples': filtered_samples.to_dict(orient='records')}
        else:
            return {'samples': []}

    def _read_metadata(self):
        if self._in_type == "gwas_sub_xls":
            self._read_excel_file()
            if self._study_sheet is None:
                raise ValueError("No study sheet in metadata template")
            
        else:
            logger.error("Don't recognise that input type")

    def _read_excel_file(self):
        """
        read all the sheets store in separate metadata dataframes
        store the metadata for the accession ID in self.metadata
        """
        with pd.ExcelFile(self._in_file) as xlsx_meta:
            if 'meta' in xlsx_meta.sheet_names:
                meta_df = pd.read_excel(xlsx_meta, sheet_name='meta')
            self._get_template_version(meta_df=meta_df)
            if self._template_version < 1.8:
                self.HEADER_MAPPINGS = config.SUBMISSION_TEMPLATE_HEADER_MAP_pre1_8
            if 'study' in xlsx_meta.sheet_names:
                self._study_sheet = pd.read_excel(xlsx_meta,
                                                  sheet_name='study',
                                                  skiprows=[0, 2, 3])
                self._study_sheet.rename(columns=self.HEADER_MAPPINGS, inplace=True)
            if 'sample' in xlsx_meta.sheet_names:
                self._sample_sheet = pd.read_excel(xlsx_meta,
                                                   sheet_name='sample',
                                                   skiprows=[0, 2, 3])
                self._sample_sheet.rename(columns=self.HEADER_MAPPINGS, inplace=True)              

    def _get_sample_metadata_from_gwas_api(self):
        study_url = config.GWAS_CATALOG_REST_API_STUDY_URL + self._accession_id
        content = download_with_requests(url=study_url)
        study_metadata = json.loads(content)
        ancestries = study_metadata['ancestries']
        sample_metadata = [sample for sample in ancestries if sample['type'] == 'initial']
        formatted_sample_metadata = self._format_sample_metadata_from_api(sample_metadata)
        return formatted_sample_metadata

    def _format_sample_metadata_from_api(self, sample_metadata):
        formatted = {'samples': []}
        try:
            for sample in samples_metadata:
                formatted['samples'].append({
                   'sampleSize': sample['numberOfIndividuals'],
                   'sampleAncestry': [s['ancestralGroup'] for s in sample['ancestralGroups']]})
        except KeyError as e:
            logger.error(f"Missing key {e}")
        return formatted

    def _get_template_version(self, meta_df):
        try:
            self._template_version = float(meta_df[meta_df['Key'] == 'schemaVersion']['Value'].values[0])
            logger.debug(self._template_version)
        except IndexError:
            logger.warning('Cannot determine template version, assuming latest')

    def _write_metadata_to_file(self):
        if self._out_type == "ssf_yaml":
            with open(self._out_file, "w") as f:
                yaml.dump(self._formatted_metadata, f, encoding='utf-8')
        else:
            logger.error("Output type not recognised")

    def _dtype_conversion(self):
        data_types = defaultdict(type(""))
        data_types.update(config.YAML_DTYPES)
        study_metadata_types = {k: data_types[self._schema_obj[k].type] for k in self._schema_obj}
        return study_metadata_types

    def _format_metadata(self, record_meta, sample_records):
        """
        TODO: 
        1. read study and sample data in
        2. map headers
        3. create dict
        4. SumStatsMetadata.parse_obj(dict) to create metadata data model
        5. write model to yaml - yaml.dump(json.loads(f.json())))
        """

        print(record_meta)
        print(sample_records)
        meta_dict = {}
        record_meta.update(sample_records)
        #if self._out_type == "ssf_yaml":
        #    self._read_schema()
        #    for field, value in record_meta.items():
        #        if not isinstance(value, dict):
        #            logger.debug(f"field: {field}, value: {value}")
        #            if field in self.HEADER_MAPPINGS:
        #                key = self.HEADER_MAPPINGS[field]
        #                if key in self._schema_obj:
        #                    dtype = config.YAML_DTYPES[self._schema_obj[key].type]
        #                    # format list type fields
        #                    if dtype == list and isinstance(value, str):
        #                        seq = [v for v in value.split("|")]
        #                        logger.debug(f"seq: {seq}")
        #                        vdtype = schema_fields[key]['sequence'][0]['type']
        #                    formatted_value = [self._coerce_yaml_dtype(value=v, dtype=vdtype) for v in seq]
        #                # format the other types of fields
        #                else:
        #                    formatted_value = self._coerce_yaml_dtype(value=value, dtype=dtype)
        #                meta_dict[key] = formatted_value
        #else:
        #    logger.error("Output type not recognised")
        return meta_dict

    def _coerce_boolean(self, value):
        if str(value).lower() in {'no', 'false', 'n'}:
            return False
        elif str(value).lower() in {'yes', 'true', 'y'}:
            return True
        else:
            return value

    def _coerce_yaml_dtype(self, value, dtype):
        convert_to_type = str
        yaml_dtypes = config.YAML_DTYPES
        if dtype in yaml_dtypes:
            convert_to_type = yaml_dtypes[dtype]
            if convert_to_type == str:
                cleaned_str = self._sanitise_str(value)
                return cleaned_str
            elif convert_to_type == bool:
                return self._coerce_boolean(value)
        return convert_to_type(value)

    @staticmethod
    def _sanitise_str(string):
        encoded_str = string.encode(encoding="ascii", errors="ignore")
        decoded_str = encoded_str.decode()
        stripped = decoded_str.strip()
        no_newlines = stripped.replace('\n','')
        return no_newlines

    @staticmethod
    def _get_record_from_df(df, key, value):
        records = df[df[key] == value]
        if len(records) == 0:
            raise ValueError(f"{key}: {value} not found in metadata")
        else:
            return records

    def _read_schema(self):
        with open(self._schema_file, 'r') as f:
            schema = yaml.safe_load(f)
        self._schema_to_metadata_object(schema)
        return schema
    
    def _schema_to_metadata_object(self, schema):
        self._schema_obj = munch.Munch.fromDict(schema['mapping'])

    def __extend_metadata(self):
        self._add_id_to_meta()
        self._add_data_file_name_to_meta()
        self._add_md5_to_meta()
        self._add_defaults_to_meta()
        self._add_gwas_cat_link()

    def _add_data_file_name_to_meta(self):
        self._formatted_metadata['dataFileName'] = self._data_file_name

    def _add_id_to_meta(self):
        self._formatted_metadata['GWASID'] = self._accession_id

    def _add_md5_to_meta(self):
        self._formatted_metadata['dataFileMd5sum'] = self._md5sum

    def _add_defaults_to_meta(self):
        self._formatted_metadata['fileType'] = config.SUMSTATS_FILE_TYPE

    def _add_gwas_cat_link(self):
        self._formatted_metadata['GWASCatalogAPI'] = config.GWAS_CATALOG_REST_API_STUDY_URL + self._accession_id


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-md5sum", help='md5sum of the submitted sumstats file, which is used as a key for the metadata', required=True)
    argparser.add_argument("-id", help='GWAS accession id', required=True)
    argparser.add_argument("-in_file", help='File to read in', required=True)
    argparser.add_argument("-out_file", help='File to write metadata to', required=True)
    argparser.add_argument("-in_type", help='Type of file being read', default='gwas_sub_xls')
    argparser.add_argument("-out_type", help='Type of file to convert to', default='ssf_yaml')
    argparser.add_argument("-schema", help='Schema for output', required=True)
    argparser.add_argument("-data_file", help='Data file name', required=True)
    args = argparser.parse_args()

    """
    md5sum is used as a key to pull out the relevant information from the metadata file. 
    """
    md5sum = args.md5sum
    accession_id = args.id
    in_file = args.in_file
    out_file = args.out_file
    in_type = args.in_type
    out_type = args.out_type
    schema = args.schema
    data_file = args.data_file

    converter = MetadataConverter(accession_id=accession_id,
                                  md5sum=md5sum,
                                  in_file=in_file,
                                  out_file=out_file,
                                  in_type=in_type,
                                  out_type=out_type,
                                  schema=schema,
                                  data_file=data_file
                                  )
    converter.convert_to_outfile()


if __name__ == '__main__':
    main()
