import datetime
import requests


class SpreeApi(object):
    existed_taxons = dict()

    def __init__(self, endpoint, api_key):
        self.endpoint = endpoint
        self.api_key = api_key

    def list_orders(self, since_id=0, _id=None, since_time=None, state='complete'):
        if _id is not None:
            endpoint_url = self.append_api_key(self.endpoint + '/api/v1/orders?q[id_eq]=%s&q[state_eq]=%s' % (_id, state))
        elif since_time is not None:
            endpoint_url = self.append_api_key(
                self.endpoint + '/api/v1/orders?q[completed_at_gt]=%s&q[state_eq]=%s&q[s]=completed_at:asc' % (since_time, state))
        else:
            endpoint_url = self.append_api_key(self.endpoint + '/api/v1/orders?q[id_gt]=%s&q[state_eq]=%s' % (since_id, state))
        response = requests.get(endpoint_url)
        return response.json()

    def get_order(self, order_id):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/orders/%s' % order_id)

        return requests.get(endpoint_url).json()

    def create_product(self, product_data):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products')

        return requests.post(endpoint_url, json=product_data)

    def get_product(self, product_id):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s' % product_id)

        return requests.get(endpoint_url).json()

    def delete_product(self, product_id):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s' % product_id)

        return requests.delete(endpoint_url)

    def update_product(self, product_id, product_data):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s' % product_id)

        return requests.put(endpoint_url, json=product_data)

    def list_products(self, page, per_page=50):
        url = self.endpoint + '/api/v1/products?per_page=%s&page=%s' % (per_page, page)
        endpoint_url = self.append_api_key(url)
        try:
            return requests.get(endpoint_url).json()['products']
        except:
            return []

    def create_properties(self, product_id, name, value):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s/product_properties/%s' % (product_id, name))
        product_data = {'product_property': {'value': value}}
        return requests.put(endpoint_url, json=product_data)

    def update_property(self, product_id, name, value):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s/product_properties/%s' % (product_id, name))
        product_data = {'product_property': {'value': value}}
        return requests.put(endpoint_url, json=product_data)

    def create_property(self, product_id, name, value):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s/product_properties' % product_id)
        product_data = {'product_property': {'value': value, 'property_name': name}}
        return requests.post(endpoint_url, json=product_data)

    def create_variant(self, product_id, sku, option_value_ids, price, cost):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s/variants' % product_id)
        data = {'variant': {'sku': sku, 'price': price, 'cost_price': cost, 'option_value_ids': [option_value_ids]}}
        return requests.post(endpoint_url, json=data)

    def update_variant(self, product_id, variant_id, **params):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/products/%s/variants/%s' % (product_id, variant_id))
        data = {'variant': params}
        return requests.put(endpoint_url, json=data)

    def get_variant(self, product_id, sku, currency='USD'):
        endpoint_url = self.append_api_key(
            self.endpoint + '/api/v1/products/%s/variants?q[sku_eq]=%s&currency=%s' % (product_id, sku, currency))
        return requests.get(endpoint_url)

    def create_stock(self, variant_id, qty, stock_location=1, backorderable=False):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/stock_locations/%s/stock_items' % stock_location)
        data = {'stock_item': {'count_on_hand': qty, 'variant_id': variant_id, 'backorderable': backorderable}}
        return requests.post(endpoint_url, json=data)

    def update_stock(self, stock_item_id, qty, stock_location=1, force=True, backorderable=False):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/stock_locations/%s/stock_items/%s' % (stock_location, stock_item_id))
        data = {'stock_item': {'count_on_hand': qty, 'force': force, 'backorderable': backorderable}}
        return requests.put(endpoint_url, json=data)

    def create_taxon(self, taxonomy_id, name, parent_id=None):
        endpoint_url = self.append_api_key(self.endpoint + '/api/v1/taxonomies/%s/taxons' % taxonomy_id)
        data = {'taxon': {'name': name, 'parent_id': parent_id}}
        return requests.post(endpoint_url, json=data)

    def list_taxons(self, taxonomy_id, per_page=1):
        taxons = []
        page = 1

        while True:
            try:
                url = self.endpoint + '/api/v1/taxonomies/%s/taxons?per_page=%s&page=%s' % (taxonomy_id, per_page, page)
                endpoint_url = self.append_api_key(url)
                response = requests.get(endpoint_url)
                json_data = response.json()
                taxons.extend(json_data['taxons'])
                if len(json_data['taxons']) < per_page:
                    break
                page += 1
            except:
                continue

        taxons = self.loop_taxons(taxons, dict())

        return taxons

    def loop_taxons(self, taxons_response, taxons, parent_name=None):
        for taxon in taxons_response:
            key = taxon['name']
            if parent_name is not None:
                key = parent_name + '>' + key
            taxons[key] = taxon['id']
            if 'taxons' in taxon:
                taxons = self.loop_taxons(taxon['taxons'], taxons, key)

        return taxons

    def find_taxon_by_name(self, name, parent_id, taxonomy_id=1):
        try:
            endpoint = '%s/api/v1/taxonomies/%s/taxons?q[name_cont]=%s&without_children=1' % (self.endpoint, taxonomy_id, name)
            endpoint = self.append_api_key(endpoint)
            response = requests.get(endpoint, timeout=180).json()
            for taxon in response['taxons']:
                if taxon['parent_id'] == parent_id and taxon['name'] == name:
                    return taxon

            for taxon in response['taxons']:
                if taxon['name'] == name:
                    return taxon
        except:
            pass
        return None

    def append_api_key(self, url):
        separator = '&' if '?' in url else '?'
        return url + '%stoken=%s' % (separator, self.api_key)
