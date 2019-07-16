# coding: utf-8

import csv
import json
import re
from time import sleep

import requests
from lxml import html
from requests import Session

CAPTCHAAPI = "<API_KEY>"

SITEKEY = "<SITE_KEY>"

class TwoCaptcha(object):
    """Interface for 2Captcha API."""

    BASE_URL = "http://2captcha.com"

    def __init__(self, api_key=CAPTCHAAPI):
        self.session = Session()
        self.session.params = {"key": api_key}

    def solve_recaptcha(self, site_url, site_key, proxy=None, poll=None):
        """
        :param site_url: domain of the site with recaptcha
        :param site_key: open key on site, can be found in html source
        :param proxy
        :return: recaptcha token
        """

        payload = {
            "googlekey": site_key,
            "pageurl": site_url,
            "method": "userrecaptcha",
        }

        # post site key to get captcha ID
        if proxy:
            req = self.session.post(
                "http://2captcha.com/in.php", params=payload, proxies=proxy
            )
        else:
            req = self.session.post("http://2captcha.com/in.php", params=payload)

        captcha_id = req.text.split("|")[1]

        # retrieve response [recaptcha token]
        payload = {}
        payload["id"] = captcha_id
        payload["action"] = "get"

        if proxy:
            req = self.session.get(
                "http://2captcha.com/res.php", params=payload, proxies=proxy
            )
        else:
            req = self.session.get("http://2captcha.com/res.php", params=payload)

        recaptcha_token = req.text
        while "CAPCHA_NOT_READY" in recaptcha_token:
            sleep(5)
            req = self.session.get("http://2captcha.com/res.php", params=payload)
            recaptcha_token = req.text
        print(recaptcha_token)
        recaptcha_token = recaptcha_token.split("|")[1]
        return recaptcha_token

    def get_balance(self):
        """
        :return: account balance in USD
        """
        payload = {"action": "getbalance", "json": 1}
        response = self.session.get(url=self.BASE_URL + "/res.php", params=payload)
        JSON = response.json()
        if JSON["status"] == 1:
            balance = JSON["request"]
            return balance


def get_tree_with_captcha(session, response, site_url):
    if "distil_r_captcha" in response.text:
        headers = {
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "Referer": "https://www.funda.nl/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en,sr-RS;q=0.9,sr;q=0.8,en-US;q=0.7",
        }
        tree = html.fromstring(response.text)
        distril_url = (
            "https://www.funda.nl"
            + tree.xpath('//meta[@http-equiv="refresh"]/@content')[0].split("url=")[1]
        )
        response = session.get(distril_url, headers=headers)
        print(response.url)

        with open("captcha.html", "w") as f:
            f.write(response.text)

        tree = html.fromstring(response.text)
        post_url = (
            "https://www.funda.nl"
            + tree.xpath('//form[@id="distilCaptchaForm"]/@action')[0]
        )
        param1 = tree.xpath(
            '//form[@id="distilCaptchaForm"]/input[@id="dCF_ticket"]/@value'
        )[0]
        param2 = tree.xpath(
            '//form[@id="distilCaptchaForm"]/input[@name="remoteip"]/@value'
        )[0]

        twocaptcha = TwoCaptcha(api_key=CAPTCHAAPI)
        g_recaptcha_response = twocaptcha.solve_recaptcha(site_url, SITEKEY)
        print(g_recaptcha_response)

        data = {
            "dCF_ticket": param1,
            "remoteip": param2,
            "g-recaptcha-response": g_recaptcha_response,
        }
        headers = {
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Origin": "https://funda.nl",
            "Upgrade-Insecure-Requests": "1",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en,sr-RS;q=0.9,sr;q=0.8,en-US;q=0.7",
        }

        response = session.post(post_url, data=data, headers=headers)
        print(response.url)

        with open("afterrecaptcha.html", "w") as f:
            f.write(response.text)

    tree = html.fromstring(response.text)

    return tree


def get_detail(session, url, headers):
    response = session.get(url, headers=headers)
    tree = get_tree_with_captcha(session, response, url)
    title = tree.xpath("//title/text()")[0]
    postal_code = re.search(r"\d{4} [A-Z]{2}", title).group(0)
    city = re.search(r"\d{4} [A-Z]{2} \w+", title).group(0).split()[2]
    address = re.findall(r"te koop: (.*) \d{4}", title)[0]
    price_dd = tree.xpath(
        "//dt[contains(text(),'Vraagprijs')]/following-sibling::dd[1]/text()"
    )[0]
    price = re.findall(r" \d+.\d+", price_dd)[0].strip().replace(".", "")

    year_built_dd = tree.xpath(
        "//dt[contains(text(),'Bouwjaar')]/following-sibling::dd[1]/text()"
    )[0]
    year_built = re.findall(r"\d+", year_built_dd)[0]
    area_dd = tree.xpath(
        "//dt[contains(text(),'Wonen')]/following-sibling::dd[1]/text()"
    )[0]
    area = re.findall(r"\d+", area_dd)[0]
    price_per_m2 = "%.2f" % (float(price) / float(area))
    rooms_dd = tree.xpath(
        "//dt[contains(text(),'Aantal kamers')]/following-sibling::dd[1]/text()"
    )[0]
    rooms = re.findall(r"\d+ kamer", rooms_dd)[0].replace(" kamer", "")
    bedrooms = re.findall(r"\d+ slaapkamer", rooms_dd)[0].replace(" slaapkamer", "")

    new_item = {}
    new_item["postal_code"] = postal_code
    new_item["address"] = address
    new_item["price"] = price
    new_item["year_built"] = year_built
    new_item["area"] = area
    new_item["rooms"] = rooms
    new_item["bedrooms"] = bedrooms
    new_item["city"] = city
    new_item["price_per_m2"] = price_per_m2

    return new_item


def main():

    output_file = open("output.csv", "w")
    FIELDS = [
        "address",
        "city",
        "postal_code",
        "price",
        "price_per_m2",
        "year_built",
        "area",
        "rooms",
        "bedrooms",
    ]

    csv_writer = csv.DictWriter(output_file, fieldnames=FIELDS)
    csv_writer.writeheader()

    session = requests.Session()
    headers = {
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
        "Referer": "https://www.funda.nl/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en,sr-RS;q=0.9,sr;q=0.8,en-US;q=0.7",
    }
    response = session.get("https://www.funda.nl/koop/amsterdam/", headers=headers)
    with open("test.html", "w") as f:
        f.write(response.text)

    tree = get_tree_with_captcha(
        session, response, "https://www.funda.nl/koop/amsterdam/"
    )

    rows = tree.xpath('//ol[@class="search-results"]/li[@class="search-result"]')
    output_items = []

    for row in rows:
        url = (
            "https://www.funda.nl"
            + row.xpath('.//a[@data-object-url-tracking="resultlist"]/@href')[0]
        )
        print(url)
        item = get_detail(session, url, headers)
        output_items.append(item)
        print(item)
        csv_writer.writerow(item)

    with open("output.json", "w") as f:
        f.write(json.dumps(output_items, indent=2))


if __name__ == "__main__":
    main()


# https://2captcha.com/2captcha-api#solving_captchas