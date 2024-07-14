from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import mysql.connector

def convert_relative_date_to_exact(date_str):
    try:
        exact_date = datetime.strptime(date_str, '%b, %Y')
        return exact_date.strftime('%Y-%m-%d')
    except ValueError:
        if 'months ago' in date_str:
            months_ago = int(date_str.split()[0])
            exact_date = datetime.now() - relativedelta(months=months_ago)
            return exact_date.strftime('%Y-%m-%d')
        elif 'days ago' in date_str:
            days_ago = int(date_str.split()[0])
            exact_date = datetime.now() - timedelta(days=days_ago)
            return exact_date.strftime('%Y-%m-%d')
        elif 'hours ago' in date_str:
            hours_ago = int(date_str.split()[0])
            exact_date = datetime.now() - timedelta(hours=hours_ago)
            return exact_date.strftime('%Y-%m-%d')
        else:
            return date_str
def get_or_insert_website(cursor, website_name):
    cursor.execute("SELECT website_id FROM websites WHERE website_name = %s", (website_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO websites (website_name) VALUES (%s)", (website_name,))
        return cursor.lastrowid

def get_or_insert_category(cursor, category_name, website_id):
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s AND website_id = %s",
                   (category_name, website_id))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO categories (category_name, website_id) VALUES (%s, %s)",
                       (category_name, website_id))
        return cursor.lastrowid

def get_or_insert_product(cursor, product_name, category_id):
    cursor.execute("SELECT product_id FROM products WHERE product_name = %s AND category_id = %s",
                   (product_name, category_id))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO products (product_name, category_id) VALUES (%s, %s)", (product_name, category_id))
        return cursor.lastrowid

def insert_review_if_not_exists(cursor, rating, title, user_name, review_date, review_text, location, product_id):
    cursor.execute("SELECT review_id FROM reviews WHERE review_text = %s AND title = %s AND product_id = %s",
                   (review_text, title, product_id))
    result = cursor.fetchone()

    if not result:
        insert_query = "INSERT INTO reviews (rating, title, user_name, review_date, review_text, location, product_id) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        data = (rating, title, user_name, review_date, review_text, location, product_id)
        cursor.execute(insert_query, data)
        print("Data inserted into MySQL database:")
        print("-" * 50)
    else:
        print("Review already exists in the database.")

def scrape_review_block(cursor, block, product_id, keywords):
    rating_elem_1 = block.find('div', {'class': 'XQDdHH Js30Fc Ga3i8K'})
    rating_elem_2 = block.find('div', {'class': 'XQDdHH Ga3i8K'})
    rating_elem_3to5 = block.find('div', {'class': 'XQDdHH Ga3i8K'})
    review_elem = block.find('p', {'class': 'z9E0IG'})
    sum_elem = block.find('div', {'class': 'ZmyHeo'})
    name_elem = block.find_all('p', {'class': '_2NsDsF AwS1CA'})[0]
    date_elem = block.find_all('p', {'class': '_2NsDsF'})[1]
    location_elem = block.find('p', {'class': 'MztJPv'})

    if (rating_elem_1 or rating_elem_2 or rating_elem_3to5) and review_elem and sum_elem and name_elem and date_elem:
        rating_elem = rating_elem_1 or rating_elem_2 or rating_elem_3to5
        rating = rating_elem.text

        review_date = convert_relative_date_to_exact(date_elem.text.strip())
        location = location_elem.text.split(',')[1].strip().replace('Certified Buyer', '').strip()

        review_text = sum_elem.text.replace('READ MORE', '').strip()
        title = review_elem.text.strip()

        review = {
            'Rating': rating,
            'Title': title,
            'User Name': name_elem.text.strip(),
            'Date': review_date,
            'Review Text': review_text,
            'Location': location
        }
        if (int(rating) in [1, 2]) or (keywords and any(
                keyword in review['Review Text'].lower() or keyword in review['Title'].lower() for keyword in
                keywords)):
            insert_review_if_not_exists(cursor, review['Rating'], review['Title'], review['User Name'],
                                        review['Date'], review['Review Text'], review['Location'],
                                        product_id)
    else:
        print("Review information not complete.")

def scrape_reviews_to_mysql_paginated(url, website_name, category_name, product_name, keywords=None):
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)

    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        website_id = get_or_insert_website(cursor, website_name)
        category_id = get_or_insert_category(cursor, category_name, website_id)
        product_id = get_or_insert_product(cursor, product_name, category_id)

        # Get the total number of pages
        driver.get(url)
        time.sleep(5)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        last_page_elem = soup.find('div', {'class': '_1G0WLw mpIySA'})
        if last_page_elem:
            last_page_span = last_page_elem.find('span')
            if last_page_span:
                last_page_text = last_page_span.text.strip()
                last_page_text = last_page_text.replace(',', '')
                last_page = int(last_page_text.split()[-1])
                print(f"Total number of pages: {last_page}")
            else:
                print("Error: Unable to find last page span.")
                return
        else:
            print("Error: Unable to find last page element.")
            return

        for page in range(1, last_page + 1):
            page_url = f"{url}&page={page}"
            driver.get(page_url)
            time.sleep(15)

            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            review_blocks = soup.find_all('div', {'class': 'col EPCmJX Ma1fCG'})

            if not review_blocks:
                print(f"No review blocks found on page {page}. Skipping to the next page.")
                continue

            for block in review_blocks:
                try:
                    scrape_review_block(cursor, block, product_id, keywords)
                except Exception as review_error:
                    print(f"Error processing review on page {page}: {str(review_error)}")

            db.commit()
            print(f"Data from page {page} inserted into MySQL database")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

    finally:
        driver.quit()
        cursor.close()
        db.close()


product_url = 'https://www.flipkart.com/dish-tv-hd-dth-bangla-1-month-royal-sports-kids-pack-set-top-box-connection-installation/product-reviews/itme7abc0c0bd400?pid=DTNFDCGN4HR9C38C&lid=LSTDTNFDCGN4HR9C38COMLHN0&marketplace=FLIPKART'
website_name = 'Flipkart'
category_name = 'Electronics'
product_name = 'Dish TV HD DTH'
keywords = ['Not recommended', 'Utterly Disappointed', 'good', 'Nice', 'awesome', 'wow', 'love', 'bad', 'excellent',
            'poor', 'best', 'love', 'adore', 'happy', 'very', 'super','joyful', 'satisfied', 'delighted', 'pleased', 'excited', 'terrible', 'horrible', 'worst', 'rare', 'great',
            'good', 'excellent', 'wonderful', 'great', 'amazing', 'fantastic', 'outstanding', 'perfect', 'love',
            'happy', 'satisfied', 'delighted', 'impressed', 'pleased', 'superb', 'bad', 'poor', 'terrible', 'Horrible',
            'worst', 'awful', 'disappointing', 'unpleasant', 'regret', 'frustrating', 'annoying', 'difficult',
            'displeased', 'Worst', 'Worthless', 'okay', 'average', 'fair', 'fine', 'decent', 'satisfactory',
            'acceptable','neutral', 'common', 'normal', 'standard', 'usual', 'moderate', 'regular', 'terrific',
            'inadequate', 'inferior', 'unsatisfactory', 'displeasing', 'repulsive', 'disgusting', 'horrid', 'lousy',
            'unimpressive', 'subpar', 'very poor']
scrape_reviews_to_mysql_paginated(product_url, website_name, category_name, product_name, keywords=keywords)