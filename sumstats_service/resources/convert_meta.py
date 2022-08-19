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
import config

class metadataConverter():
    def __init__(self, accession_id, in_file, out_file, in_type, out_type, schema):
        self.accession_id = accession_id
        self.in_file = in_file
        self.out_file = out_file
        self.in_type = in_type
        self.out_type = out_type
        self.schema = schema
        self.metadata = None
        self.formatted_metadata = None


    def read_metadata_from_file(self):
        if self.in_type == "gwas_sub_xls":
            self.metadata = self.read_excel_file()
        else:
            print("Don't recognise that input type")

    def read_excel_file(self):
        """
        read all the sheets store in separate metadata dataframes
        store the metadata for the accession ID in self.metadata
        """
        study_df = pd.read_excel(self.in_file, sheet_name='study',
                                 skiprows=[0, 2, 3])
        sample_df = pd.read_excel(self.in_file, sheet_name='sample',
                                  skiprows=[0, 2, 3])
        merged_df = pd.merge(study_df, sample_df, on="Study tag")
        return merged_df


    def write_metadata_to_file(self):
        self.formatted_metadata = self.format_metadata()
        with open(self.out_file, "w") as f:
            f.write(self.formatted_metadata)

    def format_metadata(self):
        """
        format the metadata - might need schema here - where is it defined?
        """
        formatted_metadata = None
        if self.out_type == "ssf_yaml":
            # read schema - possible to have a validator function to return meta schema?
            # format metadata according to schema
            return formatted_metadata
        else:
            print("Don't recognise that output type")

    def read_schema(self):
        # return the schema
        pass

    def convert_to_outfile(self):
        self.read_metadata_from_file()
        print(self.metadata)
        #self.write_metadata_to_file()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-id", help='Accession ID', required=True)
    argparser.add_argument("-in_file", help='File to read in', required=True)
    argparser.add_argument("-out_file", help='File to write metadata to', required=True)
    argparser.add_argument("-in_type", help='Type of file being read', default='gwas_sub_xls')
    argparser.add_argument("-out_type", help='Type of file to convert to', default='ssf_yaml')
    argparser.add_argument("-schema", help='Schema for output')
    args = argparser.parse_args()
    accession_id = args.id
    in_file = args.in_file
    out_file = args.out_file
    in_type = args.in_type
    out_type = args.out_type
    schema = args.schema

    converter = metadataConverter(accession_id=accession_id,
                                  in_file=in_file,
                                  out_file=out_file,
                                  in_type=in_type,
                                  out_type=out_type,
                                  schema=schema)
    converter.convert_to_outfile()


if __name__ == '__main__':
    main()
