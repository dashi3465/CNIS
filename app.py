from flask import Flask, render_template, request, Response
import mysql.connector
import csv
import io
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from nltk.sentiment import SentimentIntensityAnalyzer
from collections import Counter


app = Flask(__name__)


def get_website_id(cursor, website_name):
    cursor.execute("SELECT website_id FROM websites WHERE website_name = %s", (website_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None


def get_category_id(cursor, category_name, website_id):
    cursor.execute("SELECT category_id FROM categories WHERE category_name = %s AND website_id = %s",
                   (category_name, website_id))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None


def get_product_id(cursor, product_name, category_id):
    cursor.execute("SELECT product_id FROM products WHERE product_name = %s AND category_id = %s",
                   (product_name, category_id))
    result = cursor.fetchone()
    if result:
        print(f"Product found. Product ID: {result[0]}")
        return result[0]
    else:
        print("Product not found.")
        return None


@app.route('/')
def index():
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        # Fetch dynamic values for website, category, and product
        cursor.execute("SELECT DISTINCT website_name FROM websites")
        websites = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT category_name FROM categories")
        categories = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT product_name FROM products")
        products = [row[0] for row in cursor.fetchall()]

        return render_template('HTML/index.html', websites=websites, categories=categories, products=products)

    except Exception as e:
        return render_template('HTML/index.html', websites=[], categories=[], products=[], error=str(e))

    finally:
        cursor.close()
        db.close()


@app.route('/about')
def about():
    return render_template('HTML/about.html')


@app.route('/freelancer')
def freelancer():
    return render_template('HTML/freelancer.html')


@app.route('/search', methods=['POST'])
def search():
    website_name = request.form['websiteName']
    category_name = request.form['categoryName']
    product_name = request.form['productName']

    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        website_id = get_website_id(cursor, website_name)
        if website_id is None:
            return render_template('HTML/index.html', results=None, error="Website not found.")

        category_id = get_category_id(cursor, category_name, website_id)
        if category_id is None:
            return render_template('HTML/index.html', results=None, error="Category not found.")

        product_id = get_product_id(cursor, product_name, category_id)
        if product_id is None:
            return render_template('HTML/index.html', results=None, error="Product not found.")

        query = "SELECT DISTINCT location FROM reviews WHERE product_id = %s"
        cursor.execute(query, (product_id,))
        locations = [row[0] for row in cursor.fetchall()]
        locations.sort()

        query = "SELECT * FROM reviews WHERE product_id = %s"
        cursor.execute(query, (product_id,))
        results = cursor.fetchall()

        sia = SentimentIntensityAnalyzer()
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        for review in results:
            text = review[5]
            sentiment_score = sia.polarity_scores(text)
            if sentiment_score['compound'] > 0:
                positive_count += 1
            elif sentiment_score['compound'] < 0:
                negative_count += 1
            else:
                neutral_count += 1

        sentiment_data = {}
        for review in results:
            location = review[6]
            if location not in sentiment_data:
                sentiment_data[location] = {'positive': 0, 'negative': 0, 'neutral': 0}
            text = review[5]
            sentiment_score = sia.polarity_scores(text)
            if sentiment_score['compound'] > 0:
                sentiment_data[location]['positive'] += 1
            elif sentiment_score['compound'] < 0:
                sentiment_data[location]['negative'] += 1
            else:
                sentiment_data[location]['neutral'] += 1

        top_locations = sorted(sentiment_data.keys(), key=lambda x: sum(sentiment_data[x].values()), reverse=True)[:5]
        labels = top_locations
        positive_percentages = [sentiment_data[loc]['positive'] / sum(sentiment_data[loc].values()) * 100 for loc in
                                top_locations]
        negative_percentages = [sentiment_data[loc]['negative'] / sum(sentiment_data[loc].values()) * 100 for loc in
                                top_locations]
        neutral_percentages = [sentiment_data[loc]['neutral'] / sum(sentiment_data[loc].values()) * 100 for loc in
                               top_locations]

        plt.figure(figsize=(10, 6))
        index = range(len(labels))
        bar_width = 0.3
        plt.bar(index, positive_percentages, bar_width, color='green', label='Positive')
        plt.bar([i + bar_width for i in index], negative_percentages, bar_width, color='red', label='Negative')
        plt.bar([i + 2 * bar_width for i in index], neutral_percentages, bar_width, color='blue', label='Neutral')
        plt.xlabel('Location')
        plt.ylabel('Percentage')
        plt.title('Sentiment Analysis for Top Locations')
        plt.xticks([i + bar_width for i in index], labels)
        plt.legend()
        plt.grid(False)

        img_data = BytesIO()
        plt.savefig(img_data, format='png')
        img_data.seek(0)

        encoded_img_data = base64.b64encode(img_data.getvalue()).decode('utf-8')

        return render_template('HTML/search.html', results=results, locations=locations, productId=product_id,
                               chart_data=encoded_img_data, positive_count=positive_count,
                               negative_count=negative_count, neutral_count=neutral_count, error=None)

    except Exception as e:
        return render_template('HTML/search.html', results=None, error=str(e))

    finally:
        cursor.close()
        db.close()


@app.route('/filter_reviews', methods=['POST'])
def filter_reviews():
    selected_location = request.form['location']
    product_id = request.form['productId']
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        query = "SELECT DISTINCT location FROM reviews WHERE product_id = %s"
        cursor.execute(query, (product_id,))
        locations = [row[0] for row in cursor.fetchall()]

        if selected_location:
            query = "SELECT * FROM reviews WHERE location = %s AND product_id = %s"
            cursor.execute(query, (selected_location, product_id))
            results = cursor.fetchall()
        else:
            query = "SELECT * FROM reviews WHERE product_id = %s"
            cursor.execute(query, (product_id,))
            results = cursor.fetchall()

        sentiments = []

        for review in results:
            text = review[5]
            sentiment = analyze_sentiment(text)
            sentiments.append(sentiment)

        sentiment_counts = Counter(sentiments)
        positive_count = sentiment_counts['positive']
        negative_count = sentiment_counts['negative']
        neutral_count = sentiment_counts['neutral']

        non_zero_counts = [count for count in [positive_count, negative_count, neutral_count] if count > 0]

        minority_reviews = []
        minority_count = 0

        if len(non_zero_counts) > 1:
            min_reviews = min(non_zero_counts)
            for review, sentiment in zip(results, sentiments):
                if (min_reviews == positive_count and sentiment == 'positive') or \
                   (min_reviews == negative_count and sentiment == 'negative') or \
                   (min_reviews == neutral_count and sentiment == 'neutral'):
                    minority_reviews.append(review)
                    minority_count += 1

        total_reviews = len(results)
        positive_percentage = round((positive_count / total_reviews) * 100) if total_reviews > 0 else 0
        negative_percentage = round((negative_count / total_reviews) * 100) if total_reviews > 0 else 0
        neutral_percentage = round((neutral_count / total_reviews) * 100) if total_reviews > 0 else 0

        labels = ['Positive', 'Negative', 'Neutral']
        counts = [positive_count, negative_count, neutral_count]
        colors = ['green', 'red', 'blue']

        plt.figure(figsize=(6, 4))
        plt.bar(labels, counts, color=colors)
        plt.ylabel('Number of Reviews')
        plt.title('Sentiment Analysis')

        img_data = BytesIO()
        plt.savefig(img_data, format='png')
        img_data.seek(0)

        encoded_img_data = base64.b64encode(img_data.getvalue()).decode('utf-8')

        return render_template('HTML/freelancer.html', results=results, locations=locations,
                               positive_count=positive_count, negative_count=negative_count,
                               neutral_count=neutral_count, minority_reviews=minority_reviews,
                               positive_percentage=positive_percentage, negative_percentage=negative_percentage,
                               neutral_percentage=neutral_percentage, total_reviews=total_reviews,
                               error=None, productId=product_id, chart_data=encoded_img_data,
                               minority_count=minority_count)

    except Exception as e:
        return render_template('HTML/freelancer.html', results=None, locations=None, error=str(e))

    finally:
        cursor.close()
        db.close()


def analyze_sentiment(text):
    sia = SentimentIntensityAnalyzer()
    sentiment_score = sia.polarity_scores(text)

    if sentiment_score['compound'] > 0.05:
        return 'positive'
    elif sentiment_score['compound'] < -0.05:
        return 'negative'
    else:
        return 'neutral'


@app.route('/download_csv', methods=['POST'])
def download_csv():
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        query = "SELECT * FROM reviews"
        cursor.execute(query)
        reviews = cursor.fetchall()

        csv_data = [
            ['review_id', 'Rating', 'Title', 'User Name', 'Review Date', 'Review Text', 'Location', 'product_id']]
        for review in reviews:
            csv_data.append(list(review))

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_data)

        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = 'attachment; filename=reviews.csv'
        return response

    except Exception as e:
        return str(e)

    finally:
        cursor.close()
        db.close()


@app.route('/biased_reviews')
def biased_reviews():
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = 5000
        offset = (page - 1) * per_page

        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        cursor.execute("SELECT COUNT(user_name) FROM (SELECT user_name FROM reviews GROUP BY user_name HAVING COUNT(*) >= 2) AS users_with_two_reviews")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT DISTINCT user_name FROM reviews GROUP BY user_name HAVING COUNT(*) >= 2 LIMIT %s OFFSET %s", (per_page, offset))
        users = [row[0] for row in cursor.fetchall()]

        db.close()

        return render_template('HTML/biased_reviews.html', users=users, total_users=total_users, per_page=per_page, current_page=page)

    except Exception as e:
        return render_template('HTML/biased_reviews.html', error=str(e))

from flask import request, render_template

@app.route('/filtered_reviews', methods=['POST'])
def filtered_reviews():
    try:
        selected_user = request.form['user-select']

        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="cnis"
        )
        cursor = db.cursor()

        cursor.execute("""
            SELECT r.*, p.product_name 
            FROM reviews r 
            JOIN products p ON r.product_id = p.product_id 
            WHERE r.user_name = %s
        """, (selected_user,))
        reviews = cursor.fetchall()

        db.close()

        return render_template('HTML/filtered_reviews.html', reviews=reviews)

    except Exception as e:
        return render_template('HTML/filtered_reviews.html', error=str(e))




if __name__ == '__main__':
    app.run(debug=True)
