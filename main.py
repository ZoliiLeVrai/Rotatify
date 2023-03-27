from flask import Flask, render_template, send_file, redirect, request, session, jsonify, Blueprint
import os
from pymongo import MongoClient, TEXT
from pymongo.server_api import ServerApi
import time
from datetime import datetime, timedelta
import paramiko
from captcha.image import ImageCaptcha
import random
import string
import base64
import numpy as np
from io import BytesIO
from PIL import Image
import requests
import sys
import hashlib
import uuid
from captcha.image import ImageCaptcha
import re
from requests.structures import CaseInsensitiveDict
from coinbase_commerce.client import Client
from coinbase_commerce.error import WebhookInvalidPayload, SignatureVerificationError
from coinbase_commerce.webhook import Webhook
from threading import Thread
import socket

## INIT SERVER ##
app = Flask(__name__,
        static_url_path='', 
        static_folder='static',
        template_folder='templates')
app.config.update(
    SECRET_KEY='###################',
    SESSION_COOKIE_SECURE=True,
)


cb_client = Client(api_key="###################")
client = MongoClient("#####################", server_api=ServerApi('1'))

# Base de donnée
db = client['phoxycloud']
coll_account = db['account']
coll_sim = db['sim']
coll_proxy = db['proxy']
coll_checkout = db['checkout']
coll_port = db['port']

quota_reduction_step = [
    {'a': 0, 'b': 24.99, 'reduction': 0 },
    {'a': 25, 'b': 49.99, 'reduction': 21 },
    {'a': 50, 'b': 99.99, 'reduction': 47 },
    {'a': 100, 'b': 1000, 'reduction': 73 }
]

def getFreePortAndClaim():

    port = coll_port.find({'free':True}).limit(1)
    free_port = port[0]['port']

    print('Free port : ' + str(free_port))

    coll_port.update_one({'port': free_port}, {'$set': {
        'free': False
    }});
    return free_port

def bytesto(bytes, to, bsize=1024):
    a = {'k' : 1, 'm': 2, 'g' : 3, 't' : 4, 'p' : 5, 'e' : 6 }
    r = float(bytes)
    for i in range(a[to]):
        r = r / bsize
    return(r)

def str2bool(v):
    return v.lower() in ("true")

def generateCaptcha():
    captcha_text = ''.join(random.choice(string.ascii_uppercase) for i in range(5))
    image = ImageCaptcha(width = 280, height = 70)
    im_file = image.generate(captcha_text)
    im_bytes = im_file.getvalue() 
    im_b64 = base64.b64encode(im_bytes).decode('utf-8')
    session['captcha'] = hashlib.sha256(str(captcha_text+"37443aba-37a4-4814-ad20-88ed64c46d96").encode('utf-8')).hexdigest()
    return im_b64

def sessionIsValid():
    try:
        X = session['X']
        Y = session['Y']
        Z = session['Z']
        session_reponse = list(coll_account.find({'session_uuid': Z}))
        if len(session_reponse) > 0:
            if X == hashlib.sha224(str.encode(session_reponse[0]['username'])).hexdigest():
                if Y == session_reponse[0]['password']:
                    return True
        return False
    except:
        return False

def getUserInfo():
    try:
        X = session['X']
        Y = session['Y']
        Z = session['Z']
        session_reponse = list(coll_account.find({'session_uuid': Z}))
        if len(session_reponse) > 0:
            if X == hashlib.sha224(str.encode(session_reponse[0]['username'])).hexdigest():
                if Y == session_reponse[0]['password']:
                    return session_reponse[0]
        return False
    except:
        return False

@app.route('/exit/')
def exit():
    session['X'] = ""
    session['Y'] = ""
    session['Z'] = ""
    return redirect('/')

@app.route('/')
def accueil():
    return render_template('index.html')

@app.route('/connexion/')
def connexion():
    if sessionIsValid() == False:
        im_b64 = generateCaptcha()
        return render_template('connexion.html', captcha=im_b64)
    else:
        return redirect('/accueil')

@app.route('/inscription/')
def inscription():
    if sessionIsValid() == False:
        im_b64 = generateCaptcha()
        return render_template('inscription.html', captcha=im_b64)
    else:
        return redirect('/connexion')

@app.route('/auth/inscription/', methods=['POST'])
def auth_inscription():

    if sessionIsValid() == True:
        return jsonify(success=False, msg="Vous avez déjà un compte.")

    try:
        username = request.form['username'].lower()
        password = request.form['password']
        captcha = request.form['captcha'].upper()
    except:
        return jsonify(success=False, msg="Entrez vos Identifiants.")

    username = re.sub('\W+','', username)

    if session['captcha'] !=  hashlib.sha256(str(captcha+"37443aba-37a4-4814-ad20-88ed64c46d96").encode('utf-8')).hexdigest():
        im_b64 = generateCaptcha()
        return jsonify(success=False, msg="Captcha invalide.", captcha=im_b64)

    if len(username) < 3:
        return jsonify(success=False, msg="Nom d'utilisateur trop court.")

    if len(username) > 15:
        return jsonify(success=False, msg="Nom d'utilisateur trop long.")

    if len(password) < 3:
        return jsonify(success=False, msg="Mot de passe trop court.")

    if len(password) > 50:
        return jsonify(success=False, msg="Mot de passe trop long.")

    register_reponse = list(coll_account.find({'username': username}))

    if len(register_reponse) > 0:
        im_b64 = generateCaptcha()
        return jsonify(success=False, msg="Nom d'utilisateur déjà utilisé.", captcha=im_b64)

    session_uuid =  str(uuid.uuid4())
    coll_account.insert_one({
        "uuid":str(uuid.uuid4()),
        "session_uuid":session_uuid,
        "username":username,
        "password":hashlib.sha224(str.encode(password)).hexdigest(),
        "balance":0,
        "quota_bytes":0,
        "ban":False,
        "admin":False,
        "enabled":True
    });

    session['X'] = hashlib.sha224(str.encode(username)).hexdigest()
    session['Y'] = hashlib.sha224(str.encode(password)).hexdigest()
    session['Z'] = str(session_uuid)

    return jsonify(success=True)

@app.route('/auth/connexion/', methods=['POST'])
def auth_connexion():

    try:
        username = request.form['username'].lower()
        password = request.form['password']
        captcha = request.form['captcha'].upper()
    except:
        return jsonify(success=False, msg="Entrez vos Identifiants.")

    if session['captcha'] !=  hashlib.sha256(str(captcha+"37443aba-37a4-4814-ad20-88ed64c46d96").encode('utf-8')).hexdigest():
        im_b64 = generateCaptcha()
        return jsonify(success=False, msg="Captcha invalide.", captcha=im_b64)

    login_reponse = list(coll_account.find({'username': username, 'password': hashlib.sha224(str.encode(password)).hexdigest()}))

    if len(login_reponse) == 0:
        im_b64 = generateCaptcha()
        return jsonify(success=False, msg="Identifiants invalide.", captcha=im_b64)

    session['X'] = hashlib.sha224(str.encode(username)).hexdigest()
    session['Y'] = hashlib.sha224(str.encode(password)).hexdigest()
    session['Z'] = str(login_reponse[0]['session_uuid'])

    return jsonify(success=True)

@app.route('/accueil/')
def dashboard():
    if sessionIsValid() == False:
        return redirect('/connexion')
    else:
        userInfo = getUserInfo()

        proxy_list = list(coll_proxy.find({'owner_id':userInfo['uuid'], 'ended': False}))
        proxy_list_ended = list(coll_proxy.find({'owner_id':userInfo['uuid'], 'ended': True}))

        return render_template('dashboard.html', userInfo=userInfo, proxy_list=proxy_list, proxy_list_ended=proxy_list_ended)

@app.route('/crédit/')
def buy():
    if sessionIsValid() == False:
        return redirect('/connexion')
    else:
        bussy_sim = list(coll_sim.find({'$or':[ {'status':'created'}, {'status':'pending'}]}))
        for sim in bussy_sim:
            elapsed = int(time.time()) - sim['bussy_ts']
            if elapsed > 3600:
                coll_sim.update_one({'serial': sim['serial']}, {'$set': {
                    'bussy': False,
                    'bussy_by': "",
                    'status': "",
                    'id': "",
                    'days': 0,
                    'gb':0
                }});
            else:
                print('Temps ecoulé : ' + str(elapsed))

        userInfo = getUserInfo()
        return render_template('buy.html', userInfo=userInfo)          

@app.route('/boutique/')
def boutique():
    if sessionIsValid() == False:
        return redirect('/connexion')
    else:
        list_sim = list(coll_sim.find({'online':True}))
        userInfo = getUserInfo()
        return render_template('boutique.html', userInfo=userInfo, list_sim=list_sim)          

@app.route('/admin/ajouter_crédit/')
def admin_ajouter_crédit():
    if sessionIsValid() == False:
        return redirect('/connexion')
    else:
        userInfo = getUserInfo()
        if userInfo['admin'] == True:
            account = list(coll_account.find())
            return render_template('admin_add_credit.html', userInfo=userInfo, account=account)    
        else:
            return "404"      

@app.route('/admin/api/add_credit/', methods=['POST'])
def admin_api_add_credit():

    if sessionIsValid() == False:
        return jsonify(success=False, msg="Vous devez être connecté.")

    if getUserInfo()['admin'] == False:
        return jsonify(success=False, msg="Vous devez être administrateur.")

    try:
        amount = float(request.form['amount'])
        username = request.form['username']
    except Exception as e:
        return jsonify(success=False, msg="Formulaire invalide.")

    coll_account.update_one({'username': username}, {'$inc': { 'balance': amount }})

    return jsonify(success=True)

## PARTIE ADMIN ##
import public_api

if __name__ == '__main__':
    app.run(debug=True, host="127.0.0.1",port=os.getenv("PORT", default=5000))
