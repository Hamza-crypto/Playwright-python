from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pymysql
import time
import requests
import telepot


BASE_URL = "https://MY-STORE-URL.myshopify.com"
email = "email@gmail.com"
password = "password"


def send_telegram_message(message):
    token = "5830796364:AAExX1ct1aywwZGbplgqFkfFTdBq3G4iqmk"
    chat_id = "-1001876307314"
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&parse_mode=HTML&text={message}"
    try:
        requests.get(url)
    except Exception as e:
        print('Proxy not found')


def send_telegram_photo(url):
    token = "5830796364:AAExX1ct1aywwZGbplgqFkfFTdBq3G4iqmk"
    chat_id = "-1001876307314"

    try:
        bot = telepot.Bot(token)
        bot.sendPhoto(chat_id, photo=open(url, 'rb'))
    except Exception as e:
        print('Proxy not found')


def scrape(cursor):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(storage_state="auth.json")
        for a in cursor:
            product_id = a[1]
            timestamp = a[2]
            processed = a[3]
            page = context.new_page()
            login(page, context, product_id)
            time.sleep(5)
            open_product_page(page, cursor, product_id, timestamp, processed)


def login(page, context, product_id):
    page.goto(BASE_URL + '/admin/products/' + product_id)
    time.sleep(5)
    if not page.get_by_role("heading", name='Log in to Shopify').is_visible():
        print('Already logged in')
        return
    print('Logging in ...')
    page.fill('input#account_email', email)
    page.click('button[type=submit]')
    print('Email entered')
    page.fill('input#account_password', password)
    page.click('button[type=submit]')
    print('Password entered')
    context.storage_state(path="auth.json")


def open_product_page(page, cursor, product_id, timestamp, processed):
    print('Opening product page ...')
    print('clicking on Adjustment history')
    time.sleep(10)
    try:
        page.click('text=Adjustment history')
        time.sleep(10)
        print('Clicked !')
        print('Waiting for 45 seconds to fully load the page')
        print(page.url)

        if page.get_by_text('No adjustments made to inventory').is_visible():
            print('No adjustments made to inventory')
            query = "DELETE FROM ih_webhooks where data = '{product_id}'".format(product_id=product_id)
            print(query)
            cursor.execute(query)


        table = page.query_selector('table')

        print('Printing table')
        tables = BeautifulSoup(table.inner_html(), 'html.parser')
        for table in tables:
            for row in table.find_all('tr'):
                col_count = 0
                activity, adjusted_by, incremented_by, total = '', '', 0, 0
                print('col')
                for col in row.find_all('td'):
                    value = col.text.strip().replace(',', '')
                    print(value)
                    if col_count == 0:
                        activity = value
                    elif col_count == 1:
                        adjusted_by = value
                    elif col_count == 3:
                        incremented_value = value.split('(')[1].split(')')
                        incremented_by = incremented_value[0]
                        total = incremented_value[1]

                    print(value)
                    col_count += 1

                if activity == '':
                    continue
                print(activity, adjusted_by, incremented_by, total)
                query = (
                    "INSERT INTO `ih_adjustment_history` (`id`,`product_id`, `date`, `activity`, `adjusted_by`, `incremented_by`, `total`) VALUES (NULL, %s, %s, %s, %s, %s, %s);")
                print(query)
                cursor.execute(query, (product_id, timestamp, activity, adjusted_by, incremented_by, total))
                print('------------------')
                break

        print('waiting for next product')
        query = "DELETE FROM ih_webhooks where data = '{product_id}'".format(product_id=product_id)
        print(query)
        cursor.execute(query)
        print('connection committed')
        send_telegram_message(product_id)
        # path = f'''{product_id}.png'''
        # page.screenshot(path=path)
        # send_telegram_photo(path)
    except Exception as e:
        if processed == 1:
            query = "DELETE FROM ih_webhooks where data = '{product_id}'".format(product_id=product_id)
        else:
            query = "UPDATE `ih_webhooks` SET `processed` = '1' WHERE data = '{product_id}'".format(product_id=product_id)
        print(query)
        cursor.execute(query)
        print(e)

        message = f'<b>{product_id}    Error</b>'
        send_telegram_message(message)
        path = f'''{product_id}.png'''
        page.screenshot(path=path)
        send_telegram_photo(path)
        import os
        os.remove(path)


connection = pymysql.connect(host='0.0.0.0', user='shopify', passwd='', database='shopify')
# connection = pymysql.connect(host='localhost', user='root', passwd='', database='shopify_store')
cursor = connection.cursor()

product_id = 1235
activity = 'test'
adjusted_by = 'Bot user'
incremented_by = +1
total = 6

query = (
    "INSERT INTO `ih_adjustment_history` (`id`,`product_id`, `date`, `activity`, `adjusted_by`, `incremented_by`, `total`) VALUES (NULL, %s, NOW(), %s, %s, %s, %s);")
print(query)
cursor.execute(query, (product_id, activity, adjusted_by, incremented_by, total))

query = ("SELECT * FROM `ih_webhooks` WHERE processed = 0 ORDER BY id ASC")
number_of_records = cursor.execute(query)
print(number_of_records)
if number_of_records > 0:
    print('Opening browser ...')
    scrape(cursor)
else:
    query = ("SELECT * FROM `ih_webhooks` WHERE processed = 1 ORDER BY id ASC")
    number_of_records = cursor.execute(query)
    print(number_of_records)
    scrape(cursor)

connection.commit()
connection.close()
print('connection closed')





