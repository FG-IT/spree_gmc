#!/usr/bin/python
import argparse
import socket
import sys
import traceback
import os
import datetime

lib_dir = (os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')) + '/')
sys.path.insert(0, lib_dir)

from lib.models import Store, ShopifyProduct, Product
from lib.utils.process_checker import check_process
from shopping.content import common, _constants


def create_product(shopify_product, shopify_store, product, target_country='US', stock='in stock'):
    title = product.title
    brand = product.brand
    if brand is not None and brand not in title:
        title = title + ' by ' + brand

    link = '%s/products/%s' % (shopify_store.website, shopify_product.slug)
    if shopify_product.variant_id > 0:
        link += '?variant_id=%s' % shopify_product.variant_id

    product_attr = {
        'offerId': shopify_product.shopify_id,
        'title': title,
        'brand': brand,
        'description': product.description,
        'link': link,
        'imageLink': shopify_product.image,
        'contentLanguage': _constants.CONTENT_LANGUAGE,
        'targetCountry': target_country.upper(),
        'channel': _constants.CHANNEL,
        'availability': stock,
        'condition': shopify_product.condition,
        'price': {
            'value': float(shopify_product.price) * 1.5,
            'currency': 'USD'
        },
        'salePrice': {
            'value': float(shopify_product.price),
            'currency': 'USD'
        }
    }

    upc = None
    if product.upc is not None:
        upcs = product.upc.split(',')
        upc = upcs[0]
        if len(upc) > 0:
            product_attr['gtin'] = upc
    elif product.mpn is not None:
        product_attr['mpn'] = product.mpn

    if (upc is None or len(upc) == 0) and ('mpn' not in product_attr or product_attr['mpn'] is None or len(product_attr['mpn']) == 0):
        return None

    return product_attr


def fetch_products_from_db(site, last_id, type):
    if type == 'dated':
        last_updated = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        price_updated = last_updated
    else:
        last_updated = datetime.datetime.utcnow() - datetime.timedelta(hours=0)
        price_updated = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

    return ShopifyProduct.select().where(ShopifyProduct.shopify_name == site,
                                         ShopifyProduct.shopify_id > 0,
                                         ShopifyProduct.id > last_id,
                                         (ShopifyProduct.google_last_checked < last_updated) | (ShopifyProduct.google_last_checked == None),
                                         (ShopifyProduct.com_price_last_checked > price_updated) | (
                                                 ShopifyProduct.com_price_last_checked == None)
                                         ).limit(batch_limit).order_by(ShopifyProduct.id.asc())


def process_product(shopify_product, store, country, merchant_id, service):
    product = Product.get(Product.asin == shopify_product.asin)
    stock = 'in stock' if shopify_product.price > 0 else 'out of stock'

    google_product = create_product(shopify_product, store, product, stock=stock, target_country=country)
    if google_product is None:
        return

    try:
        request = service.products().insert(merchantId=merchant_id, body=google_product)
        result = request.execute()
        print('Product with offerId "%s"  for target country %s was created, price is %s, local %s' %
              (result['offerId'], country, result['salePrice']['value'], shopify_product.price))
    except:
        print(traceback.format_exc())
        print(google_product)

    shopify_product.google_last_checked = datetime.datetime.utcnow()
    shopify_product.save()


def parse_args():
    parser = argparse.ArgumentParser(description='Add products to google merchant center')
    parser.add_argument('-s', '--site', type=str, help='site id')
    parser.add_argument('-l', '--limit', type=int, default=100000, help='limit')
    parser.add_argument('-t', '--type', type=str, default='dated', help='all / dated')
    parser.add_argument('-c', '--country', type=str, default='us', help='us,uk')
    parser.add_argument('-asin', '--asin', type=str, default=None, help='asin')
    command_args = parser.parse_args()
    return command_args


def get_lock(process_name):
    if sys.platform.find("win"):
        return

    global lock_socket  # Without this our lock gets garbage collected
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind('\0' + process_name)
        print('I got the lock for %s' % (process_name))
    except socket.error:
        print('lock exists')
        sys.exit()


if __name__ == '__main__':
    args = parse_args()

    check_process([os.path.basename(__file__), args.site], hours=3)
    store = Store.get(site_name=args.site)
    if store is None:
        print("No store info for " + args.site + " found")
        sys.exit()

    last_id = 0
    max_limit = args.limit
    batch_limit = 100 if max_limit > 100 else max_limit
    service, config, _ = common.init(store, __doc__)
    merchant_id = store.merchant_id
    country = args.country

    if args.asin is not None:
        product = ShopifyProduct.get(ShopifyProduct.asin == args.asin)
        process_product(product, store, country, merchant_id, service)
        sys.exit()

    while True:
        products = fetch_products_from_db(args.site, last_id, args.type)
        if len(products) == 0:
            print('no products available')
            break

        for product in products:
            last_id = product.id
            process_product(product, store, country, merchant_id, service)
