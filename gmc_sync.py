from lib import logger
from lib.SpreeApiWrapper import SpreeApi
from lib.config_loaders import IniConfigLoader
from lib.feed_file_iterator import FeedFileIterator
from shopping.content import common


def run():
    default_file_path = 'config.ini'
    config = IniConfigLoader(default_file_path)

    config.set_section('gmc')
    merchant_id = config.get('merchant_id')

    config.set_section('spree')
    api_token = config.get('api_token')
    endpoint = config.get('endpoint')
    spree_api = SpreeApi(endpoint, api_token)

    service, config, _ = common.init(merchant_id)
    print(config)

    per_page = 50
    page = 1
    while True:
        products = spree_api.list_products(page, per_page)
        for product in products:
            try:
                google_merchant_id = product['google_merchant_id']
                product_type = get_product_types(product['classifications'])
                google_product = {
                    'offerId': product['google_merchant_id'],
                    'availability': 'in stock',
                    'price': {
                        'value': float(product['price']),
                        'currency': 'USD'
                    },
                    'contentLanguage': 'en',
                    'targetCountry': 'US',
                    'channel': 'online',
                    'title': product['name'].title(),
                    'brand': product['main_brand'],
                    'gtin': product['barcode'],
                    'description': product['description'],
                    'link': 'https://everymarket.com/products/' + product['slug'],
                    'imageLink': product['google_main_image'],
                    'condition': 'new',
                    'productTypes': product_type
                }
                print(product['google_merchant_id'].split('_')[-1])
                if google_product['gtin'] is None or len(google_product['gtin']) == 0:
                    google_product['mpn'] = product['google_merchant_id'].split('_')[-1]
                    print(google_product['mpn'])
                # print(get_product_types(product['classifications']))
                request = service.products().insert(merchantId=merchant_id, body=google_product)
                result = request.execute()
                logger.info("%s", result)
            except Exception as e:
                logger.exception(e)

        if len(products) < per_page:
            break
        page += 1


def get_product_types(classifications):
    result = []
    pretty_names = [c['taxon']['pretty_name'] for c in classifications]
    for classification in classifications:
        name = classification['taxon']['pretty_name']
        parent = False
        for pretty_name in pretty_names:
            if name in pretty_name and name != pretty_name:
                parent = True
                break
        if not parent:
            c = classification['taxon']['pretty_name'].replace('->', '>').replace('Department > ', '').replace('Categories > ', '').replace(
                'Categories', '')
            if len(c) > 0:
                result.append(c)
    return ', '.join(sorted(result, key=len, reverse=True)[0: 5])


if __name__ == '__main__':
    run()
