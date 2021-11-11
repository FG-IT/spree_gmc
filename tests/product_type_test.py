from gmc_sync import get_product_types
from lib.SpreeApiWrapper import SpreeApi
from lib.config_loaders import IniConfigLoader

if __name__ == '__main__':
    default_file_path = '../config.ini'
    config = IniConfigLoader(default_file_path)

    config.set_section('spree')
    api_token = config.get('api_token')
    endpoint = config.get('endpoint')
    spree_api = SpreeApi(endpoint, api_token)
    products = spree_api.list_products(1, 10)
    for product in products:
        product_type = get_product_types(product['classifications'])
        print(product_type)
