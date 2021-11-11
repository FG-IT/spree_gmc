from lib import logger
from lib.SpreeApiWrapper import SpreeApi
from lib.SpreeImporter import SpreeProductImporter
from lib.config_loaders import IniConfigLoader
from lib.feed_file_iterator import FeedFileIterator


def run():
    default_file_path = 'config.ini'
    config = IniConfigLoader(default_file_path)

    config.set_section('spree')
    api_token = config.get('api_token')
    endpoint = config.get('endpoint')
    spree_api = SpreeApi(endpoint, api_token)
    file_iterator = FeedFileIterator('data/em2.csv')
    mapping = {}
    for lines in file_iterator.read_butch(100, ','):
        if len(lines) == 0:
            break
        for line in lines:
            mapping[line['id']] = line['cat']

    importer = SpreeProductImporter(spree_api, taxonomy_id=67,
                                    root_category_id=304)

    per_page = 100
    page = 1
    while True:
        products = spree_api.list_products(page, per_page)
        for product in products:
            try:
                google_merchant_id = product['google_merchant_id']
                if google_merchant_id not in mapping:
                    logger.error("%s cat not found", google_merchant_id)
                    continue

                cat = mapping[google_merchant_id]
                categories = cat.split(' > ')
                importer.update_taxons(product['slug'], [categories])

                logger.info("%s %s", product['slug'], categories)
            except Exception as e:
                logger.exception(e)

        if len(products) < per_page:
            break
        page += 1


if __name__ == '__main__':
    run()
