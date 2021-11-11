from lib import logger



def save_product_info(product_converter):
    try:
        p = Product.get(Product.asin == product_converter.get_asin())
    except Exception as e:
        p = Product()
        p.asin = product_converter.get_asin()

    p.title = product_converter.get_title()
    p.brand = product_converter.get_brand()
    p.image = product_converter.get_image()
    p.binding = product_converter.get_binding()
    p.description = product_converter.get_description()
    p.upc = product_converter.get_upc()

    try:
        p.mpn = product_converter.get_mpn()
    except:
        pass
    p.save()


def save_shopify_product(shopify_product, site_name, product_type='product'):
    for variant in shopify_product.variants:
        try:
            product = ShopifyProduct.get(ShopifyProduct.shopify_name == site_name,
                                         ShopifyProduct.asin == variant.barcode,
                                         ShopifyProduct.sku == variant.sku)
            action = 'update'
        except:
            product = ShopifyProduct()
            action = 'created'

        product.shopify_name = site_name
        product.shopify_id = shopify_product.id
        product.asin = variant.barcode
        product.sku = variant.sku
        product.variant_id = variant.id
        product.inventory_item_id = variant.inventory_item_id
        product.slug = shopify_product.handle
        product.price = variant.price
        product.product_type = product_type
        if 'used' in variant.sku.lower():
            product.condition = 'Used'

        try:
            product.image = shopify_product.images[0].src
        except:
            pass
        product.save()

        logger.info("%s %s %s %s", product.asin, product.sku, product.shopify_id, action)


def save_spree_product(site_name, sku, price, variant_id, inventory_item_id, product_converter, product_type='product', slug=None,
                       image=None):
    try:
        product = ShopifyProduct.get(ShopifyProduct.shopify_name == site_name,
                                     ShopifyProduct.asin == product_converter.get_asin(),
                                     ShopifyProduct.sku == sku)
        action = 'update'
        product.status = 1
    except:
        product = ShopifyProduct()
        action = 'created'

    product.shopify_name = site_name
    product.shopify_id = variant_id
    product.asin = product_converter.get_asin()
    product.sku = sku
    product.slug = slug if slug is not None else product_converter.get_handle()
    product.com_price = None
    product.price = price
    product.product_type = product_type
    product.variant_id = variant_id
    product.inventory_item_id = inventory_item_id
    if 'used' in sku.lower():
        product.condition = 'Used'

    try:
        product.image = image if image is not None else product_converter.get_image()
    except:
        pass
    product.save()

    logger.info("%s %s %s %s", product.asin, product.sku, product.shopify_id, action)
