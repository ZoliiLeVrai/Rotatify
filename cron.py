from flask import Flask, render_template, send_file, redirect, request, session, jsonify, Blueprint
import os
from pymongo import MongoClient, TEXT
from pymongo.server_api import ServerApi
import time
from datetime import datetime, timedelta
from captcha.image import ImageCaptcha
import random
import string
import base64
import numpy as np
from io import BytesIO
from PIL import Image
import requests
import sys
import uuid
import re
import math

client = MongoClient("################", server_api=ServerApi('1'))

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

previous_date_time = datetime.now().date()

while True:

    proxy_list = list(coll_proxy.find({'started': True, 'ended': False}))

    for proxy in proxy_list:
        if proxy['current_quota_bytes'] > proxy['previous_quota_bytes_factured']:


            quota_step = math.ceil(proxy['previous_quota_bytes_factured'] / 1073741824)
            reduction = 0
            for k in quota_reduction_step:
                if quota_step >= k['a'] and quota_step <= k['b']:
                    reduction = int(k['reduction'])

            coll_proxy.update_one({'uuid': proxy['uuid']}, {'$inc': {
                'previous_quota_bytes_factured': 1073741824
            }});

            # Récupération des information de la sim (prix par jours et prix par Go)
            sim = list(coll_sim.find({'uuid': proxy['sim']}))

            # Récupération du solde du compte
            acc = list(coll_account.find({'uuid': proxy['owner_id']}))

            final_price = sim[0]['price_go'] - (sim[0]['price_go'] * reduction / 100)

            # Vérification du solde
            if acc[0]['balance'] >= final_price:
                # Facturer le compte propriétaire
                coll_account.update_one({'uuid': proxy['owner_id']}, {'$inc': {
                    'balance': -final_price
                }});
                print('Facturer ' + str(final_price) + " €")

                # Mettre a jour le cout du proxy
                coll_proxy.update_one({'uuid': proxy['uuid']}, {'$inc': {
                    'cost': final_price
                }});
            else:
                # Mettre a jour le proxy sur ended:True
                coll_proxy.update_one({'uuid': proxy['uuid']}, {'$set': {
                    'ended': True,
                    'end_ts': int(time.time())
                }});

                # Arrêter le docker du proxy
                print( os.system('docker stop ' + str(proxy['docker_id'])) )

                # Mettre a jour le la sim sur claim;False
                coll_sim.update_one({'uuid': proxy['sim']}, {'$set': {
                    'claim': False
                }});

                # Rendre el port de nouveau disponible
                coll_port.update_one({'port': proxy['port']}, {'$set': {
                    'free': True
                }});


    if previous_date_time != datetime.now().date():
        print('facturer un nouveau jour a tout les proxy ouvert')

        # Reset le quota de sim tout les 1er du mois
        if datetime.now().day == 1:
            for sim in list(coll_sim.find()):
                coll_sim.update_one({'uuid':sim['uuid']}, {'$set': {
                    'current_quota_bytes': 0
                }});
            for proxy in list(coll_proxy.find({'started': True, 'ended': False})):
                coll_proxy.update_one({'uuid':proxy['uuid']}, {'$set': {
                    'current_quota_bytes': 0
                }});

        proxy_list = list(coll_proxy.find({'started': True, 'ended': False}))
        for proxy in proxy_list:

            # Récupération des information de la sim (prix par jours et prix par Go)
            sim = list(coll_sim.find({'uuid': proxy['sim']}))

            # Récupération du solde du compte
            acc = list(coll_account.find({'uuid': proxy['owner_id']}))

            # Vérification du solde
            if acc[0]['balance'] >= sim[0]['price_day']:
                # Facturer le compte propriétaire
                coll_account.update_one({'uuid': proxy['owner_id']}, {'$inc': {
                    'balance': -sim[0]['price_day']
                }});
                print('Facturer ' + str(sim[0]['price_day']) + " €")

                # Mettre a jour le cout du proxy
                coll_proxy.update_one({'uuid': proxy['uuid']}, {'$inc': {
                    'cost': sim[0]['price_day']
                }});
            else:
                # Mettre a jour le proxy sur ended:True
                coll_proxy.update_one({'uuid': proxy['uuid']}, {'$set': {
                    'ended': True,
                    'end_ts': int(time.time())
                }});

                # Arrêter le docker du proxy
                print( os.system('docker stop ' + str(proxy['docker_id'])) )

                # Mettre a jour le la sim sur claim;False
                coll_sim.update_one({'uuid': proxy['sim']}, {'$set': {
                    'claim': False
                }});

                # Rendre el port de nouveau disponible
                coll_port.update_one({'port': proxy['port']}, {'$set': {
                    'free': True
                }});

        previous_date_time = datetime.now().date()


    time.sleep(30)