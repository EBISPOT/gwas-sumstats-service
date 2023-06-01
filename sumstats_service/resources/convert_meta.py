import argparse
import pandas as pd
import yaml
import json
from datetime import date
from packaging import version
from sumstats_service import config
import logging
from sumstats_service.resources.utils import download_with_requests
from gwas_sumstats_tools.schema.metadata import SumStatsMetadata


logging.basicConfig(level=logging.DEBUG, format='(%(levelname)s): %(message)s')
logger = logging.getLogger(__name__)


class MetaModel(SumStatsMetadata):
    """Inherit from the Sumstats Metadata class.
    We do this to change the config so that 
    we can serialise without the Enums.
    """
    class Config(SumStatsMetadata.Config):
        use_enum_values = True
        

class MetadataConverter:
    HEADER_MAPPINGS = config.SUBMISSION_TEMPLATE_HEADER_MAP
    STUDY_FIELD_TO_SPLIT = config.STUDY_FIELD_TO_SPLIT
    STUDY_FIELD_BOOLS = config.STUDY_FIELD_BOOLS
    SAMPLE_FIELD_TO_SPLIT = config.SAMPLE_FIELD_TO_SPLIT
    SAMPLE_FIELD_BOOLS = config.SAMPLE_FIELD_BOOLS

    def __init__(self,
                 accession_id,
                 md5sum,
                 in_file,
                 out_file,
                 data_file,
                 in_type='gwas_sub_xls',
                 out_type='ssf_yaml',
                 genome_assembly=None):
        self._accession_id = accession_id
        self._md5sum = md5sum
        self._in_file = in_file
        self._out_file = out_file
        self._in_type = in_type
        self._out_type = out_type
        self._genome_assembly = genome_assembly
        self._data_file_name = data_file
        self._metadata = None
        self._formatted_metadata = None
        self._template_version = None
        self._study_sheet = None
        self._sample_sheet = None
        self._study_record = {}
        self._sample_records = {'samples': []}
        self._schema_obj = None
        self.metadata = None

    def convert_to_outfile(self):
        if self._in_file:
            self._read_metadata()
            try:
                self._study_record = self._get_study_record()
            except ValueError as e:
                logger.error(e)
                self._in_file = None
        self._get_sample_metadata()
        self.metadata = self._create_metadata_model(self._study_record,
                                                    self._sample_records)
        if self.metadata:
            logger.debug("writing to file")
            self._write_metadata_to_file()

    def _get_study_record(self):
        key = 'md5 sum'
        records = self._get_record_from_df(df=self._study_sheet,
                                           key=key,
                                           value=self._md5sum)
        if len(records) > 1:
            raise ValueError(f"more than 1 record found \
                in metadata for key {key}")
        else:
            # remove fields without values
            records.dropna(axis='columns', inplace=True)
            for field in self.STUDY_FIELD_TO_SPLIT:
                if field in records:
                    records[field] = self._split_field(records[field])
            for field in self.STUDY_FIELD_BOOLS:
                if field in records:
                    records[field] = self._normalise_bool(records[field])
            records = self._normalise_missing_values(records)
            return records
    
    @staticmethod    
    def _split_field(field: pd.Series, delimiter: str = "|") -> pd.Series:
        return field.str.split(pat=delimiter)
    
    @staticmethod
    def _normalise_bools(field: pd.Series) -> pd.Series:
        bool_map = {"yes": True,
                    "y": True,
                    "true": True,
                    "no": False,
                    "n": False,
                    "false": False}
        field_lower = field.str.lower()
        return field_lower.map(bool_map, na_action='ignore')
    
    @staticmethod
    def _normalise_missing_values(df: pd.DataFrame) -> pd.DataFrame:
        return df.replace(["", "#NA", "NA", "N/A", "NaN", "NR"], None)

    def _get_sample_metadata(self):
        if self._sample_sheet is None or self._in_file is None:
            self._sample_records = self._get_sample_metadata_from_gwas_api()
        else:
            self._sample_records = self._get_sample_records()

    def _get_sample_records(self):
        study_tag_key = 'Study tag'
        if self._sample_sheet is not None:
            study_tag = self._study_record[study_tag_key].values[0]
            sample_records = self._get_record_from_df(df=self._sample_sheet,
                                                      key=study_tag_key,
                                                      value=study_tag)
            filtered_samples = self._get_record_from_df(df=sample_records,
                                                        key='Stage',
                                                        value='discovery',
                                                        casematch=False)
            if len(filtered_samples) > 0:
                filtered_samples.dropna(axis='columns', inplace=True)
                for field in self.SAMPLE_FIELD_TO_SPLIT:
                    if field in filtered_samples:
                        filtered_samples[field] = self._split_field(filtered_samples[field])
                for field in self.SAMPLE_FIELD_BOOLS:
                    if field in filtered_samples:
                        filtered_samples[field] = self._normalise_bool(filtered_samples[field])
                filtered_samples = self._normalise_missing_values(filtered_samples)
                return {'samples': filtered_samples.to_dict(orient='records')}
            else:
                return {'samples': []}
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
            if version.parse(self._template_version) < version.parse("1.8"):
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
        sample_metadata = []
        if content:
            study_metadata = json.loads(content)
            ancestries = study_metadata['ancestries']
            sample_metadata = [sample for sample in ancestries if sample['type'] == 'initial']
        formatted_sample_metadata = self._format_sample_metadata_from_api(sample_metadata)
        return formatted_sample_metadata

    def _format_sample_metadata_from_api(self, sample_metadata):
        formatted = {'samples': []}
        try:
            for sample in sample_metadata:
                formatted['samples'].append({
                   'sample_size': sample['numberOfIndividuals'],
                   'sample_ancestry': [s['ancestralGroup'] for s in sample['ancestralGroups']]})
        except KeyError as e:
            logger.error(f"Missing key {e}")
        return formatted

    def _get_template_version(self, meta_df):
        try:
            self._template_version = str(meta_df[meta_df['Key'] == 'schemaVersion']['Value'].values[0])
            logger.debug(self._template_version)
        except IndexError:
            logger.warning('Cannot determine template version, assuming latest')

    def _write_metadata_to_file(self):
        if self._out_type == "ssf_yaml":
            with open(self._out_file, "w") as f:
                yaml.dump(self.metadata.dict(exclude_unset=True), f, encoding='utf-8')
        else:
            logger.error("Output type not recognised")

    def _create_metadata_model(self, record_meta, sample_records):
        self._formatted_metadata = record_meta.to_dict(orient='records')[0] if len(record_meta) > 0 else {}
        self._extend_metadata()
        self._formatted_metadata.update(sample_records)
        return MetaModel.parse_obj(self._formatted_metadata)

    @staticmethod
    def _get_record_from_df(df, key, value, casematch: bool = True):
        if casematch is False:
            records = df[df[key].str.lower() == value.lower()]
        else:
            records = df[df[key] == value]
        if len(records) == 0:
            print(f"{key}: {value} not found in metadata")
            pass
        else:
            return records

    def _extend_metadata(self):
        self._add_id_to_meta()
        self._add_data_file_name_to_meta()
        self._add_md5_to_meta()
        self._add_defaults_to_meta()
        self._add_gwas_cat_link()
        if not self._in_file:
            self._add_genome_assembly()

    def _add_data_file_name_to_meta(self):
        self._formatted_metadata['data_file_name'] = self._data_file_name

    def _add_id_to_meta(self):
        self._formatted_metadata['gwas_id'] = self._accession_id

    def _add_md5_to_meta(self):
        self._formatted_metadata['data_file_md5sum'] = self._md5sum

    def _add_defaults_to_meta(self):
        self._formatted_metadata['file_type'] = config.SUMSTATS_FILE_TYPE if self._in_file else config.SUMSTATS_FILE_TYPE + "-incomplete-meta"
        self._formatted_metadata['date_last_modified'] = date.today()

    def _add_gwas_cat_link(self):
        self._formatted_metadata['gwas_catalog_catalog_api'] = config.GWAS_CATALOG_REST_API_STUDY_URL + self._accession_id

    def _add_genome_assembly(self):
        self._formatted_metadata['genome_assembly'] = self._genome_assembly 


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-md5sum", help='md5sum of the submitted sumstats file, which is used as a key for the metadata', required=True)
    argparser.add_argument("-id", help='GWAS accession id', required=True)
    argparser.add_argument("-in_file", help='File to read in', required=False)
    argparser.add_argument("-out_file", help='File to write metadata to', required=True)
    argparser.add_argument("-in_type", help='Type of file being read', default='gwas_sub_xls')
    argparser.add_argument("-out_type", help='Type of file to convert to', default='ssf_yaml')
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
    data_file = args.data_file

    converter = MetadataConverter(accession_id=accession_id,
                                  md5sum=md5sum,
                                  in_file=in_file,
                                  out_file=out_file,
                                  in_type=in_type,
                                  out_type=out_type,
                                  data_file=data_file
                                  )
    converter.convert_to_outfile()


if __name__ == '__main__':
    main()