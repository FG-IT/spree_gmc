import csv
import pandas as pd


class FeedFileIterator(object):
    """inventory report iterator，convert line to object record"""

    def __init__(self, feed_file_path):

        self.feed_file_path = feed_file_path

    def shuffle(self):
        df = pd.read_csv(self.feed_file_path)  # avoid header=None.
        shuffled_df = df.sample(frac=1)
        shuffled_df.to_csv(self.feed_file_path, index=False)

    def read_lines(self, delimiter='\t'):
        """input the inventory file and iterative output record-line object"""
        with open(self.feed_file_path, 'r', encoding='utf-8') as f:
            inv_reader = csv.reader(f, delimiter=delimiter)
            try:
                headers = next(inv_reader)
            except StopIteration:
                return

            for inventory_record in inv_reader:
                record_line = self.read_line(inventory_record, headers)

                yield record_line

    def read_butch(self, butch_size=100, delimiter='\t'):
        """input the inventory file and iterative output record-line object"""
        with open(self.feed_file_path, 'r', encoding='utf-8') as f:
            inv_reader = csv.reader(f, delimiter=delimiter)
            try:
                headers = next(inv_reader)
            except StopIteration:
                return

            butch = []
            for inventory_record in inv_reader:
                record_line = self.read_line(inventory_record, headers)
                butch.append(record_line)
                if len(butch) >= butch_size:
                    yield butch
                    butch.clear()
            yield butch

    def read_line(self, inventory_record_line, headers):
        return self.enumerate_headers(inventory_record_line, headers)

    def enumerate_headers(self, inventory_record, headers):
        record = {}
        try:
            # mapping the inventory_record according the headers order,and put in record dict
            for index, header in enumerate(headers):
                record[header] = inventory_record[index]
        except Exception as e:
            pass

        return record
