#!/usr/bin/python
#
# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Gets all products on the specified account."""

import argparse
import sys

from lib.models import Store
from shopping.content import common

# The maximum number of results to be returned in a page.
MAX_PAGE_SIZE = 250


def parse_args():
    parser = argparse.ArgumentParser(description='list products from google merchant center')
    parser.add_argument('-s', '--site', type=str, help='site id')
    parser.add_argument('-l', '--limit', type=int, default=100, help='limit')
    command_args = parser.parse_args()
    return command_args


if __name__ == '__main__':
    args = parse_args()

    store = Store.get(site_name=args.site)
    if store is None:
        print "No store info for " + args.site + " found"
        sys.exit()

    service, config, _ = common.init(store, __doc__)
    merchant_id = store.merchant_id
    request = service.products().list(
        merchantId=merchant_id, maxResults=MAX_PAGE_SIZE)

    while request is not None:
        result = request.execute()
        products = result.get('resources')
        if not products:
            print('No products were found.')
            break
        for product in products:
            price = float(product['price']['value'])
            print('Product "%s" with title "%s" was found,price is %s.' %
                  (product['id'], product['title'], price))

            if price <= 0:
                try:
                    product_id = product['id']
                    delete_request = service.products().delete(
                        merchantId=merchant_id, productId=product_id)
                    delete_request.execute()
                    print('Product %s was deleted.' % product_id)
                except:
                    pass
        request = service.products().list_next(request, result)
