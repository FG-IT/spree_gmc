from lib import logger
from lib.SpreeApiWrapper import SpreeApi
from lib.product_converters import EsBookConverter, EsProductConverter, AmazonProductPriceConverter, EsDvdConverter, EsCdConverter, \
    get_converter
from lib.product_lib import save_spree_product


class SpreeProductImporter(object):
    existed_tags = []
    existed_categories = dict()
    existed_authors = []
    shipping_category_id = 1
    prototype_id = 1
    tax_category_id = 1

    def __init__(self, spree_api: SpreeApi, import_taxons=True, download_images=True, shipping_category_id=1, prototype_id=1,
                 tax_category_id=1, root_category_id=1, root_category='Categories', first_level_category=None, taxonomy_id=1):
        self.spree_api = spree_api
        self.shipping_category_id = shipping_category_id
        self.prototype_id = prototype_id
        self.tax_category_id = tax_category_id
        self.root_category_id = root_category_id
        self.root_category = root_category
        self.taxonomy_id = taxonomy_id
        self.first_level_category = first_level_category
        self.import_taxons = import_taxons
        self.download_images = download_images

        if self.import_taxons:
            self.existed_categories[root_category] = root_category_id

    def process(self, product_info, source_price=0, used_price=None, roi=None, ad_cost=None):
        final_source_price = used_price if used_price is not None and used_price > 0 else source_price
        product_converter = self.get_product_converter(product_info, final_source_price)
        if not product_converter.can_upload():
            return

        product_data = self.prepare_product_data(product_converter)
        product_properties = self.prepare_properties(product_converter)
        product_data['product_properties'] = product_properties

        product_data['images'] = product_converter.get_images()

        response = self.spree_api.create_product(product_data)
        product = response.json()

        if 'errors' in product:
            logger.error("%s - %s ", product_converter.get_asin(), product['errors'])
            raise Exception("%s - %s " % (product_converter.get_asin(), product['errors']))

        if 'id' not in product:
            logger.error("%s - failed, %s", product_converter.get_asin(), product)
            raise Exception("%s - failed " % product_converter.get_asin())

        product_id = product['id']

        if self.import_taxons:
            try:
                self.update_taxons(product_id, product_converter)
            except Exception as e:
                logger.exception(e)

        self.process_variant(product, product_converter, source_price, used_price)
        return product

    def process_variant(self, product, product_converter, source_price, used_price=None):
        site_name = self.store.site_name
        product_id = product['id']
        slug = product['slug']
        product = self.spree_api.get_product(slug)
        try:
            sku = product['master']['sku']
            response = self.spree_api.get_variant(product_id, sku)
            variants = response.json()
            if 'variants' in variants and len(variants['variants']) > 0:
                variant = variants['variants'][0]
                qty = 3 if source_price > 0 else 0
                self.spree_api.update_stock(variant['stock_items'][0]['id'], qty)

                # image = variant['images'][0]['large_url']
                # if 'active_storage' in image:
                #     image = None
                save_spree_product(site_name, sku, variant['price'], variant['id'],
                                   variant['stock_items'][0]['id'],
                                   product_converter,
                                   product_type='product',
                                   slug=slug)

        except Exception as e:
            logger.exception(e)
            self.spree_api.delete_product(product_id)

    def get_product_converter(self, product_info, source_price):
        return get_converter(product_info)

    def update_taxons(self, product_id, categories):
        taxon_ids = set()
        if categories is not None:
            category_ids = self.prepare_category_ids(self.taxonomy_id, categories)
            taxon_ids.update(set(category_ids))
        else:
            taxon_ids.add(self.root_category_id)
        taxon_ids = list(taxon_ids)
        if len(taxon_ids) > 0:
            params = {'product': {'taxon_ids': taxon_ids}}
            self.spree_api.update_product(product_id, params)

    def prepare_properties(self, product_converter):
        properties = {
            'brand': product_converter.get_brand(),
            'feature_list': product_converter.get_features()
        }

        if product_converter.get("ProductGroup"):
            properties['product_group'] = product_converter.get("ProductGroup")

        if product_converter.get("Warranty"):
            properties['warranty'] = product_converter.get("Warranty")

        if product_converter.get_mpn():
            properties['part_number'] = product_converter.get_mpn()

        if product_converter.get("Size"):
            properties['size'] = product_converter.get("Size")

        if product_converter.get("Color"):
            properties['color'] = product_converter.get("Color")

        if product_converter.get("MaterialType"):
            properties['material_type'] = product_converter.get("MaterialType")

        if product_converter.get("Manufacturer"):
            properties['manufacturer'] = product_converter.get("Manufacturer")

        if product_converter.get("Model"):
            properties['model'] = product_converter.get("Model")

        if product_converter.get("Flavor"):
            properties['flavor'] = product_converter.get("flavor")

        return properties

    def prepare_product_data(self, product_converter: EsProductConverter):
        data = {
            'name': product_converter.get_title(),
            'shipping_category_id': self.shipping_category_id,
            'tax_category_id': self.tax_category_id,
            'description': product_converter.get_description(),
            'sku': product_converter.get_asin(),
            'prototype_id': self.prototype_id,
            'price': product_converter.get_price(roi=self.store.roi),
            'total_on_hand': 3 if product_converter.get_price() > 0 else 0,
            "weight": product_converter.get_weight(),
            "height": product_converter.get_height(),
            "width": product_converter.get_width(),
            "depth": product_converter.get_length(),
        }

        return {'product': data}

    def find_taxon_id(self, name, parent_id, taxonomy_id=1):
        taxon = self.spree_api.find_taxon_by_name(name, parent_id,taxonomy_id)
        return taxon['id'] if taxon is not None else None

    def prepare_category_ids(self, taxonomy_id, categories, ignore=None, replacements=None):
        if replacements is None:
            replacements = {'CDs & Vinyl': 'Music'}
        if ignore is None:
            ignore = ['Books', 'Subjects']

        if isinstance(categories, str):
            categories = categories.split(";")

        taxon_ids = [self.root_category_id]
        for category in categories:
            if isinstance(category, str):
                taxons = category.split('>')
            else:
                taxons = category

            key = self.root_category
            self.existed_categories[key] = self.root_category_id
            taxons = [t.strip() for t in taxons if t not in ignore]
            taxon_index = 0
            for taxon in taxons:
                if self.first_level_category is not None and self.first_level_category not in taxons:
                    continue

                if taxon in ignore:
                    continue

                if taxon in replacements:
                    taxon = replacements[taxon]
                if taxon == key:
                    continue

                if self.first_level_category is not None and taxon == self.first_level_category:
                    continue

                parent_key = key
                key = key + '>' + taxon if len(key) > 0 else taxon
                if key not in self.existed_categories:
                    parent_id = self.existed_categories[parent_key] if parent_key in self.existed_categories else None
                    taxon_id = self.existed_categories[key] if key in self.existed_categories else self.find_taxon_id(taxon, parent_id,
                                                                                                                      self.taxonomy_id)

                    if taxon_id is not None:
                        self.existed_categories[key] = taxon_id
                    else:
                        try:
                            res = self.spree_api.create_taxon(taxonomy_id, taxon, parent_id)
                            response = res.json()
                            self.existed_categories[key] = response['id']
                            logger.info("%s-%s", taxon, parent_id)
                        except:
                            pass

                if key in self.existed_categories:
                    taxon_ids.append(self.existed_categories[key])

                taxon_index += 1
        return taxon_ids


class SpreeDvdImporter(SpreeProductImporter):
    def get_product_converter(self, product_info, source_price):
        return EsDvdConverter(product_info, source_price)

    def prepare_properties(self, product_converter: EsDvdConverter):
        return product_converter.prepare_properties()


class SpreeBookImporter(SpreeProductImporter):
    condition_variants = {
        'used': 2,
        'new': 1
    }

    def set_conditions(self, condition_variants):
        self.condition_variants = condition_variants

    def get_product_converter(self, product_info, source_price):
        return EsBookConverter(product_info, source_price)

    def process(self, product_info, used_price=0, new_price=0, roi=None, ad_cost=None):
        product_converter = EsBookConverter(product_info)
        categories = product_converter.get('categories')
        if categories is not None and 'Books' not in str(categories) and self.root_category != 'Music':
            logger.info("%s  - %s not book", product_converter.get_asin(), categories)
            return

        try:
            product = super(SpreeBookImporter, self).process(product_info, new_price, used_price)
        except Exception as e:
            logger.exception(e)
            return

        if product is None:
            return

    def process_variant(self, product, product_converter, new_price, used_price=None):
        site_name = self.store.site_name
        product_id = product['id']
        slug = product['slug']
        try:
            prices = {'used': used_price, 'new': new_price}
            for condition, id in self.condition_variants.items():
                sku = product['master']['sku'] + '-' + condition
                price_converter = AmazonProductPriceConverter(product['master']['sku'], prices[condition])
                price = price_converter.get_price()
                response = self.spree_api.create_variant(product_id, sku, id, price, prices[condition])
                variant = response.json()

                qty = 3 if price > 0 else 0
                self.spree_api.update_stock(variant['stock_items'][0]['id'], qty)

                save_spree_product(site_name, sku, variant['price'], variant['id'],
                                   variant['stock_items'][0]['id'],
                                   product_converter,
                                   product_type='book',
                                   slug=slug)

        except Exception as e:
            logger.exception(e)
            self.spree_api.delete_product(product_id)

        logger.info("%s %s", product_id, product_converter.get_asin())

    def prepare_properties(self, product_converter):
        properties = {
            'isbn': product_converter.get_asin(),
            'isbn13': product_converter.get_upc(),
            'author': product_converter.get_author(),
            'publisher': product_converter.get_brand(),
            'format': product_converter.get_binding(),
            'publication_date': product_converter.get('PublicationDate'),
            'language': product_converter.get_language(),
            'edition': product_converter.get('Edition'),
            'page_count': product_converter.get('NumberOfPages'),
            # 'number_of_item': product_converter.get('NumberOfItems'),
            # 'label': product_converter.get('Label'),
            # 'release_date': product_converter.get('ReleaseDate'),
            # 'artist': product_converter.get('Artist'),
        }

        return properties


class SpreeCdImporter(SpreeProductImporter):
    def get_product_converter(self, product_info, source_price):
        return EsCdConverter(product_info, source_price)

    def prepare_properties(self, product_converter: EsCdConverter):
        return product_converter.prepare_properties()
