#!/usr/bin/python
import datetime
import os
import click
from lib import logger
from lib.SpreeApiWrapper import SpreeApi
from lib.config_loaders import IniConfigLoader
from shopping.content import common

MAX_PAGE_SIZE = 100


@click.command('download gmc product statuses')
@click.option('-c', '--check_expiration', type=int, default=0)
def run(check_expiration):
    default_file_path = 'config.ini'
    config = IniConfigLoader(default_file_path)

    config.set_section('gmc')
    merchant_id = config.get('merchant_id')

    config.set_section('spree')
    api_token = config.get('api_token')
    endpoint = config.get('endpoint')
    spree_api = SpreeApi(endpoint, api_token)

    service, config, _ = common.init(merchant_id)

    check_expiration = True if check_expiration > 0 else False
    request = service.productstatuses().list(
        merchantId=merchant_id, maxResults=MAX_PAGE_SIZE, destinations='Shopping')

    page_no = 1
    while request is not None:
        logger.info("processing page %s", page_no)
        result = request.execute()
        statuses = result.get('resources')
        if not statuses:
            print('No product statuses were returned.')
            break
        for stat in statuses:
            process_item(service, merchant_id, stat, check_expiration)

        request = service.productstatuses().list_next(request, result)
        page_no += 1


def remove_from_gmc(product_id, service, merchant_id):
    request = service.products().delete(merchantId=merchant_id, productId=product_id)
    request.execute()


def process_item(service, merchant_id, stat, check_expiration=False):
    if ':' not in stat['productId']:
        return

    product_id = stat['productId'].split(':')[-1]
    try:
        gmc_status = None
        for status in stat['destinationStatuses']:
            if status['destination'] == 'Shopping':
                gmc_status = status['status']
                break

        disapproved = False
        issue_description = None
        ignore_codes = ['policy_enforcement_account_disapproval',
                        'pending_phone_verification',
                        'pending_initial_policy_review',
                        'image_link_pending_crawl',
                        'homepage_not_claimed']
        if gmc_status == 'disapproved':
            for issue in stat['itemLevelIssues']:
                if issue['servability'] == 'disapproved' and issue['code'] not in ignore_codes:
                    disapproved = True
                    issue_description = issue['description']
                    break

        gmc_expiration_date = datetime.datetime.strptime(stat['googleExpirationDate'], "%Y-%m-%dT%H:%M:%SZ")
        expiring = check_expiration and gmc_expiration_date < datetime.datetime.utcnow() + datetime.timedelta(days=7)

        if expiring or disapproved:
            if gmc_status == 'disapproved':
                logger.info("%s", stat)

            if disapproved:
                logger.error("%s %s", product_id, issue_description)
                remove_from_gmc(stat['productId'], service=service, merchant_id=merchant_id)
            if expiring:
                logger.error("%s expiring %s", product_id, stat['googleExpirationDate'])
    except Exception as e:
        logger.exception(e)


if __name__ == '__main__':
    run()
