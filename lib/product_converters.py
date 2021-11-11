import html
import random
import shopify
import yaml
from bs4 import BeautifulSoup

from lib import logger

description_blacklist_keywords = ['Amazon', 'donates', 'Licensed', 'certified']


def get_converter(product_info):
    if product_info['asin'].startswith('ES'):
        return EuropaProductConverter(product_info)

    if product_info['asin'].startswith('AE'):
        return AliExpressProductConverter(product_info)

    if 'binding' in product_info and product_info['binding'] == 'Audio CD':
        return EsCdConverter(product_info)

    if 'ProductGroup' in product_info and product_info['ProductGroup'] == 'Music':
        return EsCdConverter(product_info)

    if 'binding' in product_info and product_info['binding'] == 'DVD':
        return EsCdConverter(product_info)

    if 'ProductGroup' in product_info and product_info['ProductGroup'] == 'DVD':
        return EsDvdConverter(product_info)

    if not product_info['asin'].startswith('B'):
        return EsBookConverter(product_info)

    return EsProductConverter(product_info)


def check_digit_10(isbn):
    assert len(isbn) == 9
    sum = 0
    for i in range(len(isbn)):
        c = int(isbn[i])
        w = i + 1
        sum += w * c
    r = sum % 11
    if r == 10:
        return 'X'
    else:
        return str(r)


def check_digit_13(isbn):
    if not str(isbn)[0:1].isdigit():
        return isbn
    assert len(isbn) == 12
    sum = 0
    for i in range(len(isbn)):
        c = int(isbn[i])
        if i % 2:
            w = 3
        else:
            w = 1
        sum += w * c
    r = 10 - (sum % 10)
    if r == 10:
        return '0'
    else:
        return str(r)


def convert_10_to_13(isbn):
    assert len(isbn) == 10
    prefix = '978' + isbn[:-1]
    check = check_digit_13(prefix)
    return prefix + check


def clean_html(raw_html):
    clean_text = BeautifulSoup(raw_html, "lxml").text.strip()
    return clean_text


class ShopifyConverter(object):
    def convert(self):
        raise NotImplementedError()

    def get_asin(self):
        raise NotImplementedError()

    def get_handle(self):
        raise NotImplementedError()

    def get_brand(self):
        raise NotImplementedError()

    def get_title(self):
        raise NotImplementedError()

    def get_image(self):
        raise NotImplementedError()

    def get_binding(self):
        raise NotImplementedError()

    def get_description(self):
        raise NotImplementedError()

    def get_features(self):
        raise NotImplementedError()

    def get_upc(self):
        raise NotImplementedError()

    def get_mpn(self):
        raise NotImplementedError()

    def can_upload(self):
        raise NotImplementedError()

    def get_source_price(self):
        return 0

    def get_qty(self):
        return 0

    def in_stock(self):
        return True


class EsProductConverter(ShopifyConverter):
    properties = {
        'Author': 'author',
        'Manufacture': 'manufacture',
        'Brand': 'brand',
        'Dimensions': 'dimensions',
        'Color': 'color',
        'Model': 'model',
    }

    def __init__(self, product, source_price=None, roi=0.75, ad_cost=3.0):
        self.product = product
        self.source_price = source_price
        self.asin = self.get('asin')
        self.roi = roi
        self.ad_cost = ad_cost

    def can_upload(self):
        if self.get_image() is None:
            logger.error("%s has no image", self.get_asin())
            return False
        if self.get_description() is None:
            logger.error("%s has no description", self.get_asin())
            return False
        if self.get_title() is None:
            logger.error("%s has no title", self.get_asin())
            return False
        if self.get_upc() is None and self.get_mpn() is None:
            logger.error("%s has no upc", self.get_asin())
            return False

        description = self.get_description().lower() + ' ' + self.get_title()

        for keyword in description_blacklist_keywords:
            if keyword.lower() in description:
                logger.error("Blacklist keyword %s", keyword)
                return False

        return True

    def convert(self, shopify_product=None):
        if shopify_product is None:
            shopify_product = shopify.Product()

        shopify_product.title = self.get_title()
        shopify_product.product_type = self.get('ProductGroup')
        shopify_product.vendor = self.get('brand')
        shopify_product.body_html = self.get_description()
        shopify_product.handle = self.get_handle()
        shopify_product.images = self.get_image_list()
        tags = self.get_tags()
        if tags is not None:
            shopify_product.tags = ','.join(tags)

        variants = self.get_variants()
        shopify_product.variants = variants

        return shopify_product

    def get_variants(self):
        price = self.get_price()
        v = shopify.Variant()
        v.sku = self.asin
        v.barcode = self.asin
        v.price = price
        v.weight = 1
        v.weight_unit = 'oz'
        v.inventory_quantity = 3 if price > 0 else 0
        v.old_inventory_quantity = 3 if price > 0 else 0
        # v.compare_at_price = price * 1.25
        v.inventory_management = 'shopify'
        return [v]

    def get_price(self, source_price=None, roi=None):
        if source_price is None:
            source_price = self.source_price
        if roi is None:
            roi = self.roi
        if source_price is None:
            return 0

        product_converter = AmazonProductPriceConverter(self.get_asin(), source_price, roi)
        return product_converter.price

    def get_retail_price(self):
        return self.get_price() * 1.25

    def get_asin(self):
        return str(self.asin)

    def get_sku(self):
        return self.get_asin()

    def get_title(self):
        title = self.get('title')
        if title is None or len(title) == 0:
            title = self.get('Title')
        if title is None:
            return None
        return title.replace('Amazon Exclusive', '')

    def get_handle(self):
        return create_slug(self.get_title())

    def get_brand(self):
        brand = self.get('brand')
        if brand is not None:
            brand = brand.replace('Visit the ', '')
        return brand

    def get_image(self):
        try:
            return self.get_images()[0]
        except:
            pass

    def get_binding(self):
        return self.get('binding')

    def get_upc(self):
        if self.get('ProductGroup') == 'Book' or self.get('binding') == 'Book' or not self.get_asin().startswith('B'):
            return self.get_asin()

        upc = self.get('upc')
        if upc is None:
            return

        if isinstance(upc, list):
            for i in upc:
                if len(i) >= 10:
                    return i
        elif ',' in upc:
            for i in upc.split(','):
                if len(i) >= 10:
                    return i
        else:
            for i in upc.split(' '):
                if len(i) >= 10:
                    return i

        return None

    def get_mpn(self):
        for attr in ['mpn', 'PartNumber', 'Model']:
            mpn = self.get(attr)
            if mpn is not None and len(mpn) > 2 and mpn.lower() != 'null':
                return mpn

        return self.get_asin()[-7:]

    def get_tags(self):
        categories = self.get('categories')
        if categories is None:
            categories = []

        tags = set()
        if isinstance(categories, str):
            categories = categories.split(";")
            ignore = ['Books', 'Subjects']

            for category in categories:
                taxons = category.split('>')
                if 'Subjects' not in taxons:
                    continue
                for taxon in taxons:
                    if taxon in ignore:
                        continue

                    tags.add(taxon)
        else:
            for category in categories:
                if isinstance(category, str):
                    category = category.split('>')
                for taxon in category:
                    tags.add(taxon)

        google_tags = self.get("tags")
        if google_tags is not None:
            tags.update(google_tags)

        gift_categories = self.get('gift_categories')
        if gift_categories is not None:
            for gift_category in gift_categories:
                tags.add(gift_category)

        return tags

    def prepare_categories(self):
        taxons = []
        categories = self.get('categories')
        if categories is None:
            return []
        if isinstance(categories, str):
            categories = categories.split(";")

        for category in categories:
            if isinstance(category, list):
                category = '>'.join(category)

            taxons.append(category)

        return taxons

    def get_description(self):
        desc = self.get('features')
        if desc is None:
            desc = ''

        features_list = ['<li>%s</li>' % l for l in desc.split('\n')]

        for k, v in self.properties.items():
            value = self.get(v)
            if value is not None and len(value) > 0:
                features_list.append('<li>%s: %s</li>' % (k, value))

        desc = '<ul>%s</ul>' % ('\n'.join(features_list))

        description = self.get('description')
        if description is not None and len(description) > 0:
            d = html.unescape(description.strip("'").replace('\n\n', '<br/>').replace('\n', ' ').replace('\n', '<br/>'))
            desc += d
        else:

            brand = self.get_brand()
            if brand is not None and brand not in self.get_title():
                desc += "<p>%s by %s</p>" % (self.get_title(), brand)
            else:
                desc += "<p>%s</p>" % self.get_title()

        return desc

    def get_original_description(self):
        description = self.get('description')
        if description is not None and len(description) > 0:
            description = html.unescape(description.strip("'").replace('\n\n', '<br/><br/>').replace('\n', ' '))
        else:
            description = self.get('features')

        return description

    def get_features(self):
        return self.get('features')

    def get_image_list(self):
        images = self.get_images()
        if images is not None:
            try:
                return [{'src': img} for img in images]
            except:
                pass

        return None

    def get_images(self):
        images = self.get('images')
        if images is not None and len(images) > 0:
            return [opt_img(img) for img in images]

        images = self.get('image')
        if images is not None:
            return [opt_img(img) for img in images.split(';')]
        if 'attributes' in self.product:
            image = self.product['attributes']['SmallImage']['URL']['value']
            return [opt_img(image)]
        image = self.get('imUrl')
        if image is not None:
            return [opt_img(image)]
        return None

    def get_weight(self):
        if 'attributes' in self.product:
            for key in ['ItemDimensions', 'PackageDimensions']:
                try:
                    return self.product['attributes'][key]['Weight']['value']
                except:
                    pass
        return 0

    def get_weight_unit(self):
        if 'attributes' in self.product:
            for key in ['ItemDimensions', 'PackageDimensions']:
                try:
                    return self.product['attributes'][key]['Weight']['Units']['value']
                except:
                    pass
        return 0

    def get_height(self):
        if 'attributes' in self.product:
            for key in ['ItemDimensions', 'PackageDimensions']:
                try:
                    return self.product['attributes'][key]['Height']['value']
                except:
                    pass
        return 0

    def get_width(self):
        if 'attributes' in self.product:
            for key in ['ItemDimensions', 'PackageDimensions']:
                try:
                    return self.product['attributes'][key]['Width']['value']
                except:
                    pass
        return 0

    def get_length(self):
        if 'attributes' in self.product:
            for key in ['ItemDimensions', 'PackageDimensions']:
                try:
                    return self.product['attributes'][key]['Length']['value']
                except:
                    pass
        return 0

    def get_dimensions_inches(self):
        return '%s x %s x %s inches' % (self.get_length(), self.get_width(), self.get_height())

    def get_weight_with_unit(self):
        return '%s %s' % (round(self.get_weight(), 1), self.get_weight_unit())

    def get(self, attr):
        if 'get_' in attr:
            method_name = attr.lower()
            method_name_callable = getattr(self, method_name, None)

            if callable(method_name_callable):
                return method_name_callable()

        if attr in self.product:
            return self.product[attr]

        if 'attributes' in self.product and attr in self.product['attributes']:
            try:
                attr_value = self.product['attributes'][attr]
                if isinstance(attr_value, dict):
                    return attr_value['value']
                if isinstance(attr_value, list):
                    return [v['value'] for v in attr_value]
            except:
                pass
        return None


class EsDvdConverter(EsProductConverter):
    def get_actors(self):
        return [a['value'] for a in self.product['attributes']['Actor']]

    def get_director(self):
        return self.get('Director')

    def get_language(self):
        try:
            languages = self.product['attributes']['Languages']['Language']
            for language in languages:
                if language['Type']['value'] == 'Original Language':
                    return language['Name']['value']
        except:
            return None

    def get_subtitles(self):
        languages = self.product['attributes']['Languages']['Language']
        subtitles = []
        for language in languages:
            if language['Type']['value'] == 'Subtitled':
                subtitles.append(language['Name']['value'])
        return subtitles

    def get_dubbed(self):
        languages = self.product['attributes']['Languages']['Language']
        dubbed = []
        for language in languages:
            if language['Type']['value'] == 'Dubbed':
                dubbed.append(language['Name']['value'])
        return dubbed

    def get_running_time(self):
        running_time = self.product['attributes']['RunningTime']
        return running_time['value'] + ' ' + running_time['Units']['value']

    def get_original_description(self):
        description = self.get('description')
        if description is not None and len(description) > 0:
            description = html.unescape(description.strip("'").replace('\n\n', '<br/><br/>').replace('\n', ' '))
        else:
            description = self.get('title')

            description += '<br><br><strong>Director: </strong> %s' % self.get_director()
            try:
                actors = self.get_actors()
                description += '<br><strong>Actors: </strong> %s' % ', '.join(actors)
            except:
                pass
            description += '<br><strong>Language: </strong> %s' % self.get_language()
            description += '<br><strong>Format: </strong> %s' % self.get_binding()
            description += '<br><strong>Release Date: </strong> %s' % self.get('ReleaseDate')
            try:
                description += '<br><strong>Subtitles: </strong> %s' % ", ".join(self.get_subtitles()),
            except:
                pass
            description += '<br><strong>Studio: </strong> %s' % self.get('Studio')
        return description

    def prepare_properties(self):
        properties = {
            'actor': ", ".join(self.get_actors()),
            'director': self.get_director(),
            'format': self.get_binding(),
            'language': self.get_language(),
            'subtitles': ", ".join(self.get_subtitles()),
            'edition': self.get('Edition'),
            'aspect_ratio': self.get('AspectRatio'),
            'number_of_item': self.get('NumberOfItems'),
            'label': self.get('Label'),
            'release_date': self.get('ReleaseDate'),
            'theatrical_release_date': self.get('TheatricalReleaseDate'),
            'running_time': self.get_running_time(),
            'studio': self.get('Studio'),
            'audience_rating': self.get('AudienceRating'),
        }

        return properties


class EsBookConverter(EsProductConverter):
    properties = {
        'ISBN': 'asin',
        'ISBN-13': 'ISBN_13',
        'Author': 'author',
        'Publisher': 'publisher',
        'Binding': 'binding',
        'Publication Date': 'PublicationDate',
        'Language': 'language',
        'Edition': 'edition',
        'Page Count': 'pageCount'
    }

    def get_description(self):
        features_list = []
        for k, v in self.properties.items():
            value = self.get(v)
            if value is not None:
                value = str(value)
                if len(value) > 0:
                    features_list.append('<li>%s: %s</li>' % (k, value))

        desc = '<ul>%s</ul>' % ('\n'.join(features_list))
        description = self.get_original_description()
        if description is not None and len(description) > 0:
            desc += '<h3>Product Description</h3>' + html.unescape(description.strip("'").replace('\n', '<br/>'))

        return desc

    def get_original_description(self):
        description = self.get('description')

        if description is None or len(description) == 1:
            description = self.get_title()
            if self.get_author() is not None:
                description += ' by ' + self.get_author()

        if description is not None and len(description) > 0:
            description = html.unescape(description.strip("'").replace('\n\n', '<br/>').replace('\n', ' ').replace('\n', '<br/>'))

        return description

    def get_brand(self):
        publisher = self.get('Publisher')
        if publisher is not None:
            return publisher

        return self.get('publisher')

    def get_upc(self):
        isbn13 = self.get('ISBN_13')
        if isbn13 is not None:
            return isbn13

        isbn = self.get_asin()

        if isbn is None or isbn.startswith('B'):
            return None
        return convert_10_to_13(self.get_asin())

    def get_language(self):
        try:
            return str(self.product['attributes']['Languages']['Language'][0]['Name']['value']).title()
        except:
            return None

    def get_author(self):
        authors = self.get('Author')
        if authors is None:
            authors = self.get('author')
        if authors is None:
            authors = self.get('Artist')
        if authors is None:
            return self.get_brand()

        if isinstance(authors, str):
            return authors

        return ', '.join(authors)

    def convert(self, shopify_product=None, used_only=1, new_price=0, used_price=0):
        if shopify_product is None:
            shopify_product = shopify.Product()

        shopify_product.title = self.get('title')
        shopify_product.product_type = self.get('Binding')
        shopify_product.vendor = self.get_author()
        shopify_product.body_html = self.get_description()
        shopify_product.handle = self.get_handle()
        shopify_product.images = self.get_image_list()
        tags = self.get_tags()
        if tags is not None:
            shopify_product.tags = ','.join(tags)

        variants = self.condition_variants(used_only, new_price, used_price)
        shopify_product.variants = variants

        shopify_product.options = [{
            "name": "Condition",
            "values": [
                "Used",
                "New"
            ]
        }]

        shopify_product.metafields = self.meta_fields()

        return shopify_product

    def meta_fields(self):
        metafields = []
        for k, v in self.properties.items():
            value = self.get(v)
            if value is not None:
                value = str(value)
                if len(value) > 0:
                    metafield = {
                        "key": k,
                        "value": value,
                        "value_type": "string",
                        "namespace": "global"
                    }
                    metafields.append(metafield)
        return metafields

    def condition_variants(self, used_only=1, source_price_new=0, source_price_used=0):
        price_used = self.get_price(source_price_used)
        variant_used = shopify.Variant()
        variant_used.option1 = "Used"
        variant_used.sku = self.get_asin() + '-used'
        variant_used.barcode = self.get_asin()
        variant_used.price = price_used
        variant_used.weight = 1
        variant_used.weight_unit = 'oz'
        variant_used.inventory_quantity = 3 if price_used > 0 else 0
        variant_used.old_inventory_quantity = 3 if price_used > 0 else 0
        # variant_used.compare_at_price = price_used * 1.25
        variant_used.inventory_management = 'shopify'

        variants = [variant_used]

        if used_only == 0:
            price_new = self.get_price(source_price_new)
            variant_new = shopify.Variant()
            variant_new.option1 = "New"
            variant_new.sku = self.get_asin() + '-new'
            variant_new.barcode = self.get_asin()
            variant_new.price = price_new
            variant_new.weight = 1
            variant_new.weight_unit = 'oz'
            variant_new.inventory_quantity = 3 if price_new > 0 else 0
            variant_new.old_inventory_quantity = 3 if price_new > 0 else 0
            # variant_new.compare_at_price = price_new * 1.25
            variant_new.inventory_management = 'shopify'

            variants.append(variant_new)

        return variants


class EsCdConverter(EsBookConverter):
    properties = {
        'Artist': 'Artist',
        'Format': 'binding',
        'Language': 'language',
        'Studio': 'Studio',
        'Publication Date': 'PublicationDate',
    }

    def get_title(self):
        title = self.get('title')
        if title is None:
            return
        title = title.replace('Amazon Exclusive', '')
        author = self.get_author()
        if author is not None:
            title += ' by ' + self.get_author()
        binding = self.get_binding()
        if binding:
            title += ' [%s]' % binding
        return title

    def get_artist(self):
        return self.get('Artist')

    def get_original_description(self):
        description = self.get('description')

        if description is None or len(description) == 1:
            description = self.get_title()
            if self.get_artist() is not None:
                description += ' by ' + self.get_author()

        if description is not None and len(description) > 0:
            description = html.unescape(description.strip("'").replace('\n\n', '<br/>').replace('\n', ' ').replace('\n', '<br/>'))
        return description

    def prepare_properties(self):
        properties = {
            'artist': self.get_artist(),
            'publisher': self.get_brand(),
            'format': self.get_binding(),
            'publication_date': self.get('PublicationDate'),
            'language': self.get_language(),
            'edition': self.get('Edition'),
            'number_of_item': self.get('NumberOfItems'),
            'label': self.get('Label'),
            'release_date': self.get('ReleaseDate'),
            'studio': self.get('Studio'),
        }

        return properties


class AmazonProductPriceConverter(object):
    max_price = 500

    def __init__(self, asin, source_price=0.0, min_roi=0.75, ad_cost=3.5, fba=False, sales_rate=1.25, tax_rate=0.09):

        if source_price > self.max_price:
            source_price = 0
        self.source_price = source_price
        self.asin = asin
        self.min_roi = float(min_roi) if min_roi is not None else 0.75
        self.ad_cost = float(ad_cost) if ad_cost is not None else 3.0
        self.fba = fba
        self.sales_rate = sales_rate
        self.tax_rate = tax_rate

        self.price = self.parse_price()

    def get_asin(self):
        return self.asin

    def get_price(self):
        return self.price

    def parse_price(self):
        if self.source_price <= 0:
            return 0

        if self.source_price > self.max_price:
            return 0

        # price = (self.source_price + self.ad_cost) * (1 + self.tax_rate) * (1 + self.min_roi) / 0.97
        price = (self.ad_cost + self.source_price * (1 + self.tax_rate)) * (1 + self.min_roi) / 0.97
        price = max(self.source_price + 5, price)

        return round(price, 2)

    def convert(self, shopify_product):
        variant = {'sku': self.asin,
                   'barcode': self.asin,
                   'price': self.price,
                   'weight': 1,
                   'weight_unit': 'oz',
                   'inventory_quantity': 3 if self.price > 0 else 0,
                   'old_inventory_quantity': 3 if self.price > 0 else 0,
                   'inventory_management': 'shopify'
                   }

        if self.sales_rate > 0:
            variant['compare_at_price'] = self.compare_at_price()
        else:
            variant['compare_at_price'] = 0

        shopify_product.variants = [variant]

        return shopify_product

    def compare_at_price(self):
        if self.sales_rate > 0:
            return self.price * random.uniform(1.01, self.sales_rate)

        return 0


class EuropaProductConverter(EsProductConverter):

    def get_source_price(self):
        return float(self.get('wholesaleprice'))

    def get_qty(self):
        return int(self.get('availablequantity'))

    def in_stock(self):
        instock = self.get('instock')
        if instock is None:
            instock = 1
        else:
            instock = int(instock)
        return self.get_source_price() > 0 and self.get_qty() > 0 and instock > 0

    def get_price(self, source_price=None, roi=None, ad_cost=None):
        if source_price is None:
            source_price = float(self.get('wholesaleprice'))
        if roi is None:
            roi = self.roi

        if ad_cost is None:
            ad_cost = self.ad_cost
        if source_price is None:
            return 0

        product_converter = AmazonProductPriceConverter(self.get_asin(), source_price, roi, ad_cost)
        return product_converter.price

    def get_retail_price(self):
        return float(self.get('retailprice'))

    def get_asin(self):
        return 'ES%s' % str(self.get('stockcode')).zfill(8)

    def get_sku(self):
        return self.get_asin()

    def get_title(self):
        brand = self.get_brand()
        title = str(self.get('productname'))
        if brand is not None and brand.lower() not in title.lower():
            title = brand + " " + title
        if self.get('flavor'):
            title += ', ' + str(self.get('flavor'))
        if self.get('extendedsize'):
            title += ', ' + str(self.get('extendedsize'))
        elif self.get('size'):
            title += ', ' + str(self.get('size'))
        return title

    def get_handle(self):
        return create_slug(self.get_title())

    def get_brand(self):
        return str(self.get('vendorname'))

    def get_image(self):
        try:
            return self.get_images()[0]
        except:
            pass

    def get_upc(self):
        return self.get('upc')

    def get_mpn(self):
        return None

    def prepare_categories(self):
        taxons = []
        primarycategory = self.get('primarycategory')
        if primarycategory is not None:
            taxons.append(primarycategory)
        generalcategory = self.get('generalcategory')
        if generalcategory is not None:
            taxons.append(generalcategory)

        taxons = [['Sports Nutrition'] + taxon.split('/') for taxon in taxons]

        return taxons

    def get_description(self):
        desc = '<div class="container"><div class="row">'
        desc += '<div class="col-lg-7">'
        description = self.get('productdetails')
        if description is not None and len(description) > 0:
            desc += '<h4>Details</h4><p>%s</p>' % description

        directions = self.get('directions')
        if directions is not None and len(directions) > 0:
            desc += '<h4>Directions</h4><p>%s</p>' % directions

        warnings = self.get('warnings')
        if warnings is not None and len(warnings) > 0:
            desc += '<h4>Warnings</h4><p>%s</p>' % warnings
        desc += '</div>'

        try:
            desc += '<div class="col-lg-5">%s</div>' % self.get_nutrition_facts()
        except:
            pass
        desc += '</div></div>'
        return desc

    def get_nutrition_facts(self):
        nutrients = self.get('nutrient')
        if nutrients is None:
            return None

        nutrients = yaml.load(nutrients)
        nutrition_facts = '<div class="nutritionFacts__outerFrame">' \
                          '<h1 class="nutritionFacts__title">Nutrition Facts</h1>'
        nutrition_facts += '<p class="nutritionFacts__servingSize">Serving Size <span class="ng-binding">%s %s</span></p>' % (
            nutrients['SERVINGSIZETEXT'], nutrients['SERVINGSIZEUOM'])

        nutrition_facts += '<p class="nutritionFacts__servingsPerContainer">Servings Per Container <span class="ng-binding">%s</span></p>' % \
                           nutrients['SERVINGSPERCONTAINER']
        nutrition_facts += '<h2 class="nutritionFacts__amountPerServing">Amount Per Serving</h2>' \
                           '<div class="nutritionFacts__borders">' \
                           '<h3 class="nutritionFacts__dailyValueHeader">% Daily Value*</h3>'
        for nutrient in nutrients['NUTRIENTS']:
            #
            is_bold = '--Bold' if nutrient['BOLDSTYLE'] > 0 else ''
            line = '<div class="nutritionFacts__nutrient%s">%s <span class="nutritionFacts__nutrientAmount">%s <span></span> </span><span class="nutritionFacts__dailyValue">%s</span></div>' \
                   % (is_bold, nutrient['NAME'], nutrient['QUANTITY'], nutrient['DVPERCENT'])
            nutrition_facts += line
        nutrition_facts += '<div class="nutritionFacts__nutrient proprietaryBlendPaddingTop"><span class="ng-binding ng-scope"> <span class="nutritionFacts__nutrientAmount"><span></span> </span><span class="nutritionFacts__dailyValue"></span><p class="nutritionFacts__blendDetails ng-binding ng-hide" ></p></span></div>'
        nutrition_facts += '<p class="nutritionFacts__statement">*Percent Daily Values are based on a 2,000 calorie diet. Your daily value may be higher or lower depending on your calorie needs.</p>' \
                           '<div class="ng-scope">' \
                           '<span class="nutritionFacts__ingredients">Ingredients: </span>' \
                           '<span class="nutritionFacts__ingredientsList ng-binding">%s</span></div>' \
                           '</div></div>' % self.get('ingredients')

        return nutrition_facts

    def get_original_description(self):
        return self.get_features()

    def get_features(self):
        return '%s\n%s' % (self.get('productdesc'), self.get('productdetails'))

    def get_images(self):
        image = self.get('picfile')
        if image is not None:
            return [image]
        return None

    def get_weight(self):
        if 'weight' in self.product:
            try:
                return float(self.product['weight'])
            except:
                pass
        return 0

    def get_weight_unit(self):
        return 'lb'

    def get_height(self):
        if 'height' in self.product:
            try:
                return float(self.product['height'])
            except:
                pass
        return 0

    def get_width(self):
        if 'width' in self.product:
            try:
                return float(self.product['width'])
            except:
                pass
        return 0

    def get_length(self):
        if 'depth' in self.product:
            try:
                return float(self.product['depth'])
            except:
                pass
        return 0

    def get(self, attr):
        attr = attr.lower()
        if attr in self.product:
            return self.product[attr]
        return None


class AliExpressProductConverter(EsProductConverter):
    def __init__(self, product, source_price=None, roi=0.75, ad_cost=3.0):
        super().__init__(product, source_price, roi, ad_cost)
        features_list = self.get_features_list()
        for key, value in features_list.items():
            if key not in product:
                product[key] = value
        self.product = product

    def get_source_price(self):
        return float(self.get('total_cost'))

    def get_edd(self):
        try:
            return int(self.get('edd'))
        except:
            return 30

    def in_stock(self):
        return self.get_source_price() > 0 and self.get_edd() < 45

    def get_price(self, source_price=None, roi=None, ad_cost=None):
        if source_price is None:
            source_price = self.get_source_price()
        if roi is None:
            roi = self.roi

        if ad_cost is None:
            ad_cost = self.ad_cost
        if source_price is None:
            return 0

        product_converter = AmazonProductPriceConverter(self.get_asin(), source_price, roi, ad_cost)
        return product_converter.price

    def get_asin(self):
        return self.get('asin')

    def get_sku(self):
        return self.get_asin()

    def get_title(self):
        return str(self.get('title'))

    def get_handle(self):
        return create_slug(self.get_title())

    def get_brand(self):
        brand = self.get('Brand Name')
        if brand is not None:
            return brand

        brand = self.get('Brand')
        if brand is not None:
            return brand
        return self.get('brand')

    def get_image(self):
        try:
            return self.get_images()[0]
        except:
            pass

    def get_upc(self):
        product_id = self.get('upc')
        return product_id

    def get_mpn(self):
        return self.get('productId')

    def prepare_categories(self):
        taxons = []
        category = self.get('categories')
        if category is not None:
            return category

        return taxons

    def get_description(self):
        feature = '<br>'.join(['<strong>%s: </strong> %s' % (k, v) for k, v in self.get_features_list().items()])
        desc = self.get_original_description()
        if desc is not None:
            feature += '<br><br>' + desc

        return feature

    def get_original_description(self):
        desc = self.get('description')
        if desc is None:
            desc = self.get_title()
        return desc

    def get_features_list(self):
        features = self.get('features')
        feature_variations = self.get('feature_variations')
        if feature_variations is not None:
            features += feature_variations
        feature_list = dict()
        mapping = {
            'Material': 'MaterialType',
            'Model Number': 'Model',
            'Brand Name': 'Brand'
        }
        for feature in features:
            parts = feature.split(':')
            if len(parts[1]) == 0:
                continue
            k = parts[0]
            if k in mapping:
                k = mapping[k]
            feature_list[k] = parts[1]

        return feature_list

    def get_features(self):
        return ''
        # desc = self.get_original_description()
        # desc = clean_html(desc)
        # desc = desc.replace("Description:", '').replace("Features:", "").replace("Feature:", "").replace("features:", "").strip()
        # feature = desc[:250]
        # return feature
        # features = self.get_features_list()
        # feature_list = ''
        # ignore = ['color', 'brand', 'brand name', 'materialtype', 'model']
        # for feature, value in features.items():
        #     if feature.lower() in ignore:
        #         continue
        #     feature_list += '%s: %s\n' % (feature, value)
        #
        # return feature_list

    def get_images(self):
        images = self.get('images')
        if images is not None:
            return images
        return None

    def get_weight(self):
        if 'weight' in self.product:
            try:
                return float(self.product['weight'])
            except:
                pass
        return 0

    def get_weight_unit(self):
        return 'lb'

    def get_height(self):
        if 'height' in self.product:
            try:
                return float(self.product['height'])
            except:
                pass
        return 0

    def get_width(self):
        if 'width' in self.product:
            try:
                return float(self.product['width'])
            except:
                pass
        return 0

    def get_length(self):
        if 'depth' in self.product:
            try:
                return float(self.product['depth'])
            except:
                pass
        return 0

    def get(self, attr):
        if attr in self.product:
            return self.product[attr]
        return None
