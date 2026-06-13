from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date
import os

app = Flask(__name__, static_folder='.')
CORS(app)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',  # CHANGE THIS to your MySQL password
    'database': 'library_management_system'
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error: {e}")
        return None

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/dashboard')
def get_dashboard():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as count FROM Book")
        total_books = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM Book WHERE availability = TRUE")
        available_books = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM Member")
        total_members = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM Issue WHERE status = 'Issued'")
        active_issues = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM Fine WHERE paid_status = FALSE")
        pending_fines = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT i.issue_id, m.name as member_name, b.title as book_title, 
                   i.issue_date, i.due_date
            FROM Issue i
            JOIN Member m ON i.member_id = m.member_id
            JOIN Book b ON i.book_id = b.book_id
            WHERE i.status = 'Issued'
            ORDER BY i.issue_date DESC
            LIMIT 5
        """)
        recent_issues = cursor.fetchall()
        
        cursor.execute("""
            SELECT member_id, name, phone, membership_date
            FROM Member
            ORDER BY membership_date DESC
            LIMIT 5
        """)
        recent_members = cursor.fetchall()
        
        return jsonify({
            'total_books': total_books,
            'available_books': available_books,
            'total_members': total_members,
            'active_issues': active_issues,
            'pending_fines': pending_fines,
            'recent_issues': recent_issues,
            'recent_members': recent_members
        })
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/books')
def get_books():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, a.name as author_name 
            FROM Book b
            LEFT JOIN Author a ON b.author_id = a.author_id
            ORDER BY b.book_id
        """)
        books = cursor.fetchall()
        return jsonify(books)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/books/search')
def search_books():
    query = request.args.get('q', '')
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        search_param = f'%{query}%'
        cursor.execute("""
            SELECT b.*, a.name as author_name 
            FROM Book b
            LEFT JOIN Author a ON b.author_id = a.author_id
            WHERE b.title LIKE %s OR a.name LIKE %s
            ORDER BY b.book_id
        """, (search_param, search_param))
        books = cursor.fetchall()
        return jsonify(books)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/members')
def get_members():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Member ORDER BY member_id")
        members = cursor.fetchall()
        return jsonify(members)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/members', methods=['POST'])
def add_member():
    data = request.json
    if not data.get('name') or not data.get('phone'):
        return jsonify({'error': 'Name and phone are required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        membership_date = data.get('membership_date', date.today())
        cursor.execute("""
            INSERT INTO Member (name, phone, email, address, membership_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (data['name'], data['phone'], data.get('email', ''), 
              data.get('address', ''), membership_date))
        conn.commit()
        return jsonify({'message': 'Member added successfully', 'member_id': cursor.lastrowid}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/issues')
def get_issues():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.*, m.name as member_name, b.title as book_title
            FROM Issue i
            JOIN Member m ON i.member_id = m.member_id
            JOIN Book b ON i.book_id = b.book_id
            ORDER BY i.issue_date DESC
        """)
        issues = cursor.fetchall()
        return jsonify(issues)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/issues', methods=['POST'])
def issue_book():
    data = request.json
    required_fields = ['member_id', 'book_id', 'issue_date', 'due_date']
    
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT availability FROM Book WHERE book_id = %s", (data['book_id'],))
        book = cursor.fetchone()
        if not book or not book['availability']:
            return jsonify({'error': 'Book not available'}), 400
        
        cursor.execute("INSERT INTO Issue (member_id, book_id, issue_date, due_date, status) VALUES (%s, %s, %s, %s, 'Issued')", 
                      (data['member_id'], data['book_id'], data['issue_date'], data['due_date']))
        
        cursor.execute("UPDATE Book SET availability = FALSE WHERE book_id = %s", (data['book_id'],))
        conn.commit()
        return jsonify({'message': 'Book issued successfully'}), 201
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/fines')
def get_fines():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT f.*, m.name as member_name
            FROM Fine f
            JOIN Member m ON f.member_id = m.member_id
            ORDER BY f.paid_status ASC, f.fine_id DESC
        """)
        fines = cursor.fetchall()
        return jsonify(fines)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/fines/<int:fine_id>/pay', methods=['PUT'])
def pay_fine(fine_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Fine SET paid_status = TRUE, paid_date = CURDATE() WHERE fine_id = %s", (fine_id,))
        conn.commit()
        return jsonify({'message': 'Fine paid successfully'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/stats/categories')
def get_category_stats():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT category, COUNT(*) as total_books
            FROM Book
            GROUP BY category
            ORDER BY total_books DESC
        """)
        stats = cursor.fetchall()
        return jsonify(stats)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/stats/above-avg-price')
def get_above_avg_books():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT title, price
            FROM Book
            WHERE price > (SELECT AVG(price) FROM Book)
            ORDER BY price DESC
        """)
        books = cursor.fetchall()
        return jsonify(books)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/stats/authors')
def get_author_stats():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT a.name, COUNT(b.book_id) as book_count
            FROM Author a
            LEFT JOIN Book b ON a.author_id = b.author_id
            GROUP BY a.author_id, a.name
            ORDER BY book_count DESC
        """)
        stats = cursor.fetchall()
        return jsonify(stats)
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 50)
    print("Library Management System")
    print("=" * 50)
    print("Server running at: http://localhost:5000")
    print("Make sure index.html is in the same folder")
    print("=" * 50)
    app.run(debug=True, port=5000)