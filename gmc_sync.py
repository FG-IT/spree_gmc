import click

from lib import logger
from lib.SpreeApiWrapper import SpreeApi
from lib.config_loaders import IniConfigLoader
from shopping.content import common


@click.option('-p', '--product_id', type=str, default=None, help='spree product id')
@click.option('-c', '--country', type=str, default='US', help='spree product id')
def run(product_id, country):
    default_file_path = 'config.ini'
    config = IniConfigLoader(default_file_path)

    config.set_section('gmc')
    merchant_id = config.get('merchant_id')
    service, config, _ = common.init(merchant_id)

    config.set_section('spree')
    api_token = config.get('api_token')
    endpoint = config.get('endpoint')
    spree_api = SpreeApi(endpoint, api_token)

    product = spree_api.get_product(spree_api)
    brand = ''
    upc = ''
    link = ''
    image = ''
    stock = 'in stock'
    try:
        sku = product['master']['sku']
        response = spree_api.get_variant(product_id, sku)

        variants = response.json()
        if 'variants' in variants and len(variants['variants']) > 0:
            variant = variants['variants'][0]

            variant_id = variant['id']
            price = variant['price']

            # fetch product info from spree api
            google_product = {
                'offerId': variant_id,
                'availability': stock,
                'price': {
                    'value': float(price),
                    'currency': 'USD'
                },
                'contentLanguage': 'en',
                'targetCountry': country,
                'channel': 'online',
                'title': product['master']['name'],
                'brand': brand,
                'upc': upc,
                'description': product['master']['description'],
                'link': link,
                'imageLink': image,
                'condition': 'new',
            }
            request = service.products().insert(merchantId=merchant_id, body=google_product)
            result = request.execute()
            logger.info("%s", result)

    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    run()
