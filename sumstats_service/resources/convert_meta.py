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
import config

class metadataConverter():
    def __init__(self, accession_id, in_file, out_file, in_type, out_type):
        self.accession_id = accession_id
        self.in_file = in_file
        self.out_file = out_file
        self.in_type = in_type
        self.out_type = out_type
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
        pass

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
        self.write_metadata_to_file()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-id", help='Accession ID', required=True)
    argparser.add_argument("-in", help='File to read in', required=True)
    argparser.add_argument("-out", help='File to write metadata to', required=True)
    argparser.add_argument("-in_type", help='Type of file being read', default='gwas_sub_xls')
    argparser.add_argument("-out_type", help='Type of file to convert to', default='ssf_yaml')
    args = argparser.parse_args()
    in_file = args.in_file
    out_file = args.out_file
    in_type = args.in_type
    out_type = args.out_type

    converter = metadataConverter(in_file=in_file,
                                  out_file=out_file,
                                  in_type=in_type,
                                  out_type=out_type)
    converter.convert_to_outfile()


if __name__ == '__main__':
    main()
