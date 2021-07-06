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
"""Deletes several products from the specified account, in a single batch."""

import argparse
import json
import sys

from lib.models import Store, ShopifyProduct
from shopping.content import common


def parse_args():
    parser = argparse.ArgumentParser(description='delete products from google merchant center')
    parser.add_argument('-s', '--site', type=str, help='site id')
    parser.add_argument('-l', '--limit', type=int, default=100, help='limit')
    command_args = parser.parse_args()
    return command_args


if __name__ == '__main__':
    args = parse_args()

    store = Store.get(site_name=args.site)
    if store is None:
        print("No store info for " + args.site + " found")
        sys.exit()

    service, config, _ = common.init(store, __doc__)
    merchant_id = store.merchant_id
    last_id = 0
    batch_limit = 100
    while True:
        products = ShopifyProduct.select().where(ShopifyProduct.shopify_name == args.site, ShopifyProduct.shopify_id > 0,
                                                 ShopifyProduct.id > last_id).limit(
            batch_limit)

        if len(products) == 0:
            print('no products available')
            break

        # u'online:en:GB:4353697677398'
        for country in ['US']:
            product_ids = ['online:en:%s:%s' % (country, p.shopify_id) for p in products]
            last_id = products[len(products) - 1].id
            batch = {
                'entries': [{
                    'batchId': i,
                    'merchantId': merchant_id,
                    'method': 'delete',
                    'productId': v,
                } for i, v in enumerate(product_ids)],
            }

            request = service.products().custombatch(body=batch)
            result = request.execute()

            if result['kind'] == 'content#productsCustomBatchResponse':
                for entry in result['entries']:
                    errors = entry.get('errors')
                    if errors:
                        print('Errors for batch entry %d:' % entry['batchId'])
                        print(json.dumps(entry['errors'], sort_keys=True, indent=2,
                                         separators=(',', ': ')))
                    else:
                        print('Deletion of product %s (batch entry %d) successful.' %
                              (batch['entries'][entry['batchId']]['productId'],
                               entry['batchId']))

            else:
                print('There was an error. Response: %s' % result)
