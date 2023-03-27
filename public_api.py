from __main__ import *

@app.route('/api/claim/', methods=['POST'])
def api_claim():

    if sessionIsValid() == False:
        return jsonify(success=False, msg="Vous devez être connecté.")

    try:
        sim_uuid = request.form['sim_uuid']
    except Exception as e:
        print(e)
        return jsonify(success=False, msg="Entrez l'UUID du proxy souhaité.")

    userInfo = getUserInfo()
    sim = list(coll_sim.find({ 'uuid':sim_uuid }))

    # Calculer le prix du premier jours en fonction de l'heure
    price_hour = sim[0]['price_day'] / 24
    hour_left = 24 - datetime.now().hour

    sim_total_price = float( (hour_left*price_hour) + sim[0]['price_go'])
    if userInfo['balance'] >= sim_total_price:

        coll_account.update_one({'uuid': userInfo['uuid']}, {'$inc': {
            'balance': -sim_total_price
        }});

        coll_sim.update_one({'uuid': sim_uuid}, {'$set': {
            'claim': True
        }});

        free_port = getFreePortAndClaim()
        print('start proxy with port : ' + str(free_port))

        letters = string.ascii_lowercase
        coll_proxy.insert_one({
            "owner_id": userInfo['uuid'],
            "uuid" : "proxy-"+str(uuid.uuid4()),
            "sim" : sim[0]['uuid'],
            "start_ts" : int(time.time()),
            "max_quota_bytes" : int(sim[0]['max_quota_bytes'] - sim[0]['current_quota_bytes']),
            "current_quota_bytes" : 0,
            "previous_quota_bytes_factured": 1073741824,
            "started" : False,
            "ended" : False,
            "username" : "u_"+''.join(random.choice(letters) for i in range(10)),
            "password" : "p_"+''.join(random.choice(letters) for i in range(10)),
            "external_ip" : "Création",
            "port" : free_port,
            "refresh_auto" : False,
            "cost":sim_total_price
        })

        return jsonify(success=True)
    else:
        return jsonify(success=False, msg="Le solde de votre compte est trop faible.")

@app.route('/api/terminate/', methods=['POST'])
def api_terminate():

    if sessionIsValid() == False:
        return jsonify(success=False, msg="Vous devez être connecté.")

    try:
        proxy_uuid = request.form['proxy_uuid']
    except Exception as e:
        print(e)
        return jsonify(success=False, msg="Entrez l'UUID du proxy à arrêter.")

    userInfo = getUserInfo()

    # Trouver le proxy à arrêter
    proxy = list(coll_proxy.find({ 'uuid':proxy_uuid }))

    try:
        # Arrêter le docker du proxy
        print( os.system('docker stop ' + str(proxy[0]['docker_id'])) )
    except Exception as e:
        print(e)
        return jsonify(success=False, msg="Attendez que le proxy soit démarré.")

    

    # Mettre a jour le proxy sur ended:True
    coll_proxy.update_one({'uuid': proxy[0]['uuid']}, {'$set': {
        'ended': True,
        'end_ts': int(time.time())
    }});

    # Mettre a jour le la sim sur claim;False
    coll_sim.update_one({'uuid': proxy[0]['sim']}, {'$set': {
        'claim': False
    }});

    # Rendre el port de nouveau disponible
    coll_port.update_one({'port': proxy[0]['port']}, {'$set': {
        'free': True
    }});


    return jsonify(success=True)

