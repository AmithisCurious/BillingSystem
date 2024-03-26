from flask import render_template, request, redirect, session, url_for
from app import app, db
from app.models import User, Item, Bill, BillItem
from flask import jsonify, request
from datetime import datetime
from sqlalchemy import func


@app.route('/')
@app.route('/index')
def index():
    try:
        uid = session['user_id']
    except KeyError:
        return render_template('login.html')
    return render_template('index.html')


@app.route('/get_suggestions')
def get_suggestions():
    keyword = request.args.get('keyword')
    if keyword:
        suggestions = Item.query.filter(
            Item.name.ilike(f'%{keyword}%')).limit(10).all()

        suggestion_names = [item.name for item in suggestions]
        return jsonify(suggestion_names)
    else:
        return jsonify([])


@app.route('/create_bill', methods=['POST'])
def create_bill():
    bill_number = request.form['bill_number']
    user_id = session.get('user_id')

    if user_id:
        user = User.query.get(user_id)
        bill = Bill(bill_number=bill_number, user=user)
        db.session.add(bill)
        db.session.commit()

        item_name = request.form['item_name']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        bill_item = BillItem(item_name=item_name,
                             quantity=quantity, price=price, bill=bill)
        db.session.add(bill_item)
        db.session.commit()

        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))


@app.route('/submit_bill', methods=['POST'])
def submit_bill():
    if 'user_id' in session:
        user_id = session['user_id']
        data = request.json

        if data:
            items = data.get('items')
            total = data.get('total')
            new_bill = Bill(user_id=user_id, total=total)
            db.session.add(new_bill)

            for item in items:
                item_db = Item.query.filter_by(
                    name=item['name']).first()

                if item_db:
                    new_quantity = item_db.quantity - item['quantity']
                    if new_quantity >= 0:
                        item_db.quantity = new_quantity
                        bill_item = BillItem(
                            bill=new_bill, item_name=item['name'], quantity=item['quantity'], price=item['price'])
                        db.session.add(bill_item)
                    else:
                        db.session.rollback()
                        return jsonify({'error': f'Insufficient quantity available for {item["name"]}'})
                else:
                    db.session.rollback()
                    return jsonify({'error': f'Item {item["name"]} not found'})

            db.session.commit()

            return jsonify({'message': 'Bill submitted successfully'}), 200
        else:
            return jsonify({'error': 'No data received'}), 400
    else:
        return jsonify({'error': 'User not authenticated'}), 401


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()

        if user:
            session['user_id'] = user.id
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password.')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template('signup.html')


@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        name = request.form['name']
        group = request.form['group']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])

        user_id = session.get('user_id')
        if user_id:
            item = Item(name=name, group=group, quantity=quantity,
                        price=price, user_id=user_id)
            db.session.add(item)
            db.session.commit()
            return redirect(url_for('index'))
        else:
            return redirect(url_for('login'))
    return render_template('add_item.html')


@app.route('/items')
def items():
    items = Item.query.all()
    return render_template('items.html', items=items)


@app.route('/edit_item/<int:item_id>', methods=['GET'])
def edit_item(item_id):
    item = Item.query.get(item_id)
    if item:
        return render_template('edit_item.html', item=item)
    else:
        return redirect(url_for('items'))


@app.route('/update_item', methods=['POST'])
def update_item():
    item_id = request.form['id']
    name = request.form['name']
    group = request.form['group']
    price = float(request.form['price'])
    item = Item.query.get(item_id)
    if item:
        item.name = name
        item.group = group
        item.price = price
        db.session.commit()
    return redirect(url_for('items'))


@app.route('/get_item_price')
def get_item_price():
    item_name = request.args.get('item_name')
    item = Item.query.filter_by(name=item_name).first()
    if item:
        return jsonify({'price': item.price})
    else:
        return jsonify({'error': 'Item not found'})


@app.route('/filter-bills', methods=['GET', 'POST'])
def filter_bills():
    if request.method == 'POST':
        from_date_str = request.form['from_date']
        to_date_str = request.form['to_date']
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()

        print(from_date, to_date)

        filtered_bills = Bill.query.filter(
            func.date(Bill.bill_date_time) >= from_date,
            func.date(Bill.bill_date_time) <= to_date
        ).all()
        
        print(filtered_bills)

        return render_template("filtered_bills.html", bills=filtered_bills, from_date=from_date_str, to_date=to_date_str)
    else:
        return redirect("/report")


@app.route('/report')
def show_reports():
    bill = Bill.query.all()
    bill_items = BillItem.query.all()
    return render_template('report.html', bills=bill, bill_items=bill_items)


@app.route('/delete-item', methods=['GET', 'POST'])
def delete_item():
    if request.method == 'GET':
        item_id = request.args.get('item_id')

        if item_id:
            item = Item.query.get(item_id)
            if item:
                db.session.delete(item)
                db.session.commit()
                return jsonify({'message': 'Item deleted successfully'}), 200
            else:
                return jsonify({'error': 'Item not found'}), 404
        else:
            return jsonify({'error': 'Missing item_id parameter'}), 400
    else:
        return jsonify({'error': 'Method not allowed'}), 405
