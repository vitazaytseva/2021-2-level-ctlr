"""
Scrapper implementation
"""
import datetime
import json
import re
import shutil
from random import randint
from time import sleep

import requests
from bs4 import BeautifulSoup

from constants import ASSETS_PATH, CRAWLER_CONFIG_PATH, HTTP_PATTERN
from core_utils.article import Article
from core_utils.pdf_utils import PDFRawFile


class IncorrectURLError(Exception):
    """
    Seed URL does not match standard pattern
    """


class NumberOfArticlesOutOfRangeError(Exception):
    """
    Total number of articles to parse is too big
    """


class IncorrectNumberOfArticlesError(Exception):
    """
    Total number of articles to parse in not integer
    """


class Crawler:
    """
    Crawler implementation
    """

    def __init__(self, seed_urls, max_articles: int):
        self.seed_urls = seed_urls
        self.max_articles = max_articles
        self.urls = []

    def _extract_url(self, article_bs):
        urls_bs = article_bs.find_all('td', class_='views-field views-field-title table__cell')
        for url_bs in urls_bs:
            url = url_bs.find('a')['href']
            if len(self.urls) >= self.max_articles:
                break
            self.urls.append(HTTP_PATTERN + url)

    def find_articles(self):
        """
        Finds articles
        """
        for seed_url in self.seed_urls:
            sleep(randint(1, 5))
            response = requests.get(seed_url)
            if not response.ok:
                continue
            article_bs = BeautifulSoup(response.text, 'lxml')
            self._extract_url(article_bs)

    def get_search_urls(self):
        """
        Returns seed_urls param
        """
        return self.seed_urls


class HTMLParser:
    def __init__(self, article_url, article_id):
        self.article_url = article_url
        self.article_id = article_id
        self.article = Article(self.article_url, self.article_id)

    def _fill_article_with_text(self, article_bs):
        pdf_url = article_bs.find('iframe', class_='pdf')['data-src']
        pdf = PDFRawFile(pdf_url, self.article_id)
        pdf.download()
        full_text = pdf.get_text()
        if 'Литература\n' in full_text:
            text_lst = full_text.split('Литература\n')
            self.article.text = text_lst[0]
            liter_lst = re.findall(r'^\d{1,2}[\.]', text_lst[1], flags=re.MULTILINE)
            if liter_lst:
                last_source = int(liter_lst[-1].split('.')[0])
                print(f'Number of sources of {self.article_id} article is {last_source}')
            else:
                print(f'Number of sources of {self.article_id} article is 0')
        else:
            print(f'Number of sources of {self.article_id} article is 0')
            self.article.text = full_text

    def _fill_article_with_meta_information(self, article_bs):
        self.article.author = article_bs.find('span', class_='field__item-wrapper').text

        self.article.title = article_bs.find('span', class_='field field-name-title field-formatter-string '
                                                            'field-type-string field-label-hidden').text

        node_content = article_bs.find('div', class_='node__content clearfix')

        year = node_content.find('div').find_next_siblings()[2].text.strip()[:4]
        month = node_content.find('div').find_next_siblings()[2].text.strip()[8]
        self.article.date = datetime.date(int(year), int(month), 1)

        node_pages = node_content.find('div').find_next_siblings()[2].text.strip()[11:]
        lst_with_pages = [int(i) for i in node_pages.split('-')]
        print(f'Number of pages of {self.article_id} article is {lst_with_pages[1] - lst_with_pages[0] + 1}')

        topics_bs = article_bs.find_all('span', class_='field__item-wrapper')[1:]
        self.article.topics = [topic.text for topic in topics_bs]

    def parse(self):
        response = requests.get(self.article_url)
        article_bs = BeautifulSoup(response.text, 'lxml')
        self._fill_article_with_text(article_bs)
        self._fill_article_with_meta_information(article_bs)
        return self.article


def prepare_environment(base_path):
    """
    Creates ASSETS_PATH folder if not created and removes existing folder
    """
    if base_path.exists():
        if base_path.is_dir():
            shutil.rmtree(base_path)
    base_path.mkdir(parents=True)


def validate_config(crawler_path):
    """
    Validates given config
    """
    with open(crawler_path) as file:
        configuration = json.load(file)

    if 'seed_urls' not in configuration:
        raise IncorrectURLError
    if 'total_articles_to_find_and_parse' not in configuration:
        raise IncorrectNumberOfArticlesError

    http_pattern = re.compile(HTTP_PATTERN)
    for url in configuration["seed_urls"]:
        result = http_pattern.search(url)
        if not result:
            raise IncorrectURLError

    seed_urls = configuration["seed_urls"]
    total_articles_to_find_and_parse = configuration["total_articles_to_find_and_parse"]

    if not seed_urls:
        raise IncorrectURLError
    if not isinstance(total_articles_to_find_and_parse, int):
        raise IncorrectNumberOfArticlesError
    if not isinstance(seed_urls, list):
        raise IncorrectURLError
    if total_articles_to_find_and_parse <= 0:
        raise IncorrectNumberOfArticlesError
    if total_articles_to_find_and_parse > 200:
        raise NumberOfArticlesOutOfRangeError

    return seed_urls, total_articles_to_find_and_parse


if __name__ == '__main__':
    main_seed_urls, main_max_articles = validate_config(CRAWLER_CONFIG_PATH)
    prepare_environment(ASSETS_PATH)

    crawler = Crawler(main_seed_urls, main_max_articles)
    crawler.find_articles()

    for id_of_article, url_of_article in enumerate(crawler.urls):
        article_parser = HTMLParser(article_url=url_of_article, article_id=id_of_article + 1)
        sleep(randint(1, 5))
        article = article_parser.parse()
        article.save_raw()
        print(f'The {id_of_article + 1} article is done!')
    print('Done!')
