import json
import csv
import argparse
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument('--input-csv', type=str, required=True, help='The csv of template ids to be converted to a json file')
ap.add_argument('--output-filename', type=str, default='template-ids.json', help='The output json object')
args = ap.parse_args()

if not os.path.exists(args.input_csv):
    sys.stderr.write(f'Input csv {args.input_csv} does not exist')
    sys.exit(1)

output_dt = dict()
with open(args.input_csv) as csvfile:
    reader = csv.DictReader(csvfile, dialect='excel-tab')
    for row in reader:
        sbb_id = row['Id']
        name = row['Name']
        new_template_id = row['New Id']

        output_dt[new_template_id] = {'Id': sbb_id, 'Name': name}

with open(args.output_filename, 'w') as ofs:
    ofs.write(json.dumps(output_dt, indent=True, sort_keys=True))