from flask import Flask, jsonify, render_template, request, redirect, url_for

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
from flask import session as login_session
from flask import make_response
import requests
import httplib2
import json
import random
import string

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    google_id = credentials.id_token['sub']
    if result['user_id'] != google_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_google_id = login_session.get('google_id')
    if stored_access_token is not None and google_id == stored_google_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['google_id'] = google_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px; border-radius: 150px;'
    output += '-webkit-border-radius: 150px;-moz-border-radius: 150px; > '
    return output


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = "https://accounts.google.com/"
    url += "o/oauth2/revoke?token=%s " % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    # if revoke successful then delete delete login_session.
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['google_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        return redirect(url_for('showCatalog'))
    else:
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# generate state token and pass it to login.
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


# create new user and return user id of same.
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session = make_connection()
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# to get user id if you have email .
def getUserID(email):
    session = make_connection()
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Connect to Database and create database session
def make_connection():
    engine = create_engine('sqlite:///itemcatalog.db')
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    return session


# json response of entire catalog .
@app.route('/catalog.json')
def catalogJsonResponse():
    session = make_connection()
    categories = session.query(Category).all()
    catgories = []
    for category in categories:
        categoryObject = category.serialize
        categoryItems = session.query(Item).filter_by(
            category_id=category.id).all()
        itemsArray = [item.serialize for item in categoryItems]
        if len(itemsArray) > 0:
            categoryObject['Item'] = itemsArray
        catgories.append(categoryObject)
    return jsonify(Category=catgories)


# shows catalog with latest items.
@app.route('/')
@app.route('/catalog')
def showCatalog():
    showLogin = False
    user_name = ''
    if 'user_id' in login_session:
        showLogin = True
        user_name = login_session['username']
    session = make_connection()
    categories = session.query(Category).all()
    items = session.query(Item).order_by(desc(Item.created_on)).limit(10).all()
    return render_template(
        'catalog.html', categories=categories, items=items,
        showLogin=showLogin, user_name=user_name)


# shows catalog with selected category.
@app.route('/catalog/<int:category_id>')
def showCatalogWithSelectedCategory(category_id):
    showLogin = False
    user_name = ''
    if 'user_id' in login_session:
        showLogin = True
        user_name = login_session['username']
    session = make_connection()
    categories = session.query(Category).all()
    items = session.query(Item).filter_by(category_id=category_id).all()
    return render_template(
        'catalog.html', categories=categories, items=items,
        category_id=category_id, showLogin=showLogin, user_name=user_name)


# shows item with editable links if user who created is logged in.
@app.route('/catalog/item/<int:item_id>')
def showItem(item_id):
    session = make_connection()
    item = session.query(Item).filter_by(id=item_id).one()
    showLogin = False
    user_name = ''
    editable = False
    if 'user_id' in login_session:
        showLogin = True
        user_name = login_session['username']
        if login_session['user_id'] == item.user_id:
            editable = True
    return render_template(
        'showitem.html', item=item, showLogin=showLogin, user_name=user_name,
        editable=editable)


# add item option for logged in user.
@app.route('/catalog/item/add', methods=['GET', 'POST'])
def addItem():
    session = make_connection()
    if 'user_id' not in login_session:
        return redirect(url_for('showLogin'))
    if request.method == 'POST':
        newItem = Item(
            name=request.form['name'],
            description=request.form['description'],
            category_id=request.form['category'],
            user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        return redirect(url_for('showCatalog'))
    else:
        showLogin = False
        user_name = ''
        if 'user_id' in login_session:
            showLogin = True
            user_name = login_session['username']
        categories = session.query(Category).all()
        return render_template(
            'additem.html', categories=categories,
            showLogin=showLogin, user_name=user_name)


# shows item in edit option if user who created is logged in,
# else redirect to showCatalog.
@app.route('/catalog/item/<int:item_id>/edit', methods=['GET', 'POST'])
def editItem(item_id):
    session = make_connection()
    if 'user_id' not in login_session:
        return redirect(url_for('showLogin'))
    item = session.query(Item).filter_by(id=item_id).one()
    if request.method == 'POST':
        item.name = request.form['name']
        item.description = request.form['description']
        item.category_id = request.form['category']
        session.add(item)
        session.commit()
        return redirect(url_for('showCatalog'))
    else:
        showLogin = False
        user_name = ''
        if 'user_id' in login_session:
            showLogin = True
            user_name = login_session['username']
        categories = session.query(Category).all()
        return render_template(
            'edititem.html', categories=categories,
            item=item, showLogin=showLogin, user_name=user_name)


# show delete confirmation option if user who created is logged in,
# else redirect to showCatalog.
@app.route('/catalog/item/<int:item_id>/delete', methods=['GET', 'POST'])
def deleteItem(item_id):
    if 'user_id' not in login_session:
        return redirect(url_for('showLogin'))
    session = make_connection()
    item = session.query(Item).filter_by(id=item_id).one()
    if request.method == 'POST':
        session.delete(item)
        session.commit()
        return redirect(url_for('showCatalog'))
    else:
        showLogin = False
        user_name = ''
        if 'user_id' in login_session:
            showLogin = True
            user_name = login_session['username']
        return render_template(
            'deleteitem.html', item=item,
            showLogin=showLogin, user_name=user_name)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.run(host='0.0.0.0', port=8000)
